"""采样参数（temperature）的统一解析 —— 全项目唯一的解析入口。

为什么要有这一层
----------------
改造前只有一个全局 `temperature`（默认 0.7），带来三个真实问题：

  1. **教师被迫理解一个与教学无关的技术参数**。他不知道 0.7 意味着什么，
     也没有任何依据去调它 —— 调错了只会在几轮之后才发现内容不对。
  2. **一个值覆盖所有用途**。同一个 0.7 既用于「抽取结构化字段」（应当极确定），
     也用于「课堂活动构思」（需要发散）—— 两边都不是最合适的值。
  3. **内部约定会被覆盖**。任务规划（0.2）、参数修复（0.0）、结果验证（0.0）
     这些**明确指定**的值，会被全局设置悄悄顶掉。

本模块只做一件事：**按本次请求**（用途 + 阶段 + 采样模式 + 模型能力）
解析出"最终要不要发 temperature、发多少"，并把决策过程如实带回去供追踪。

刻意不做的事
------------
  - 不通过"看用户输入里有没有关键词"猜用途 —— 既不准也不可维护；
  - 不为了决定温度而新增一次模型调用；
  - **不改写全局配置**：并发任务会互相污染（A 任务的温度被 B 任务改掉）；
  - 不碰 top_p、max_tokens、模型选择与模型失败后的降级策略；
  - 不改变教学蓝图、共享知识快照、版本管理及其它业务契约。

关于这张策略表
--------------
下面的取值是**待验证的初始策略**，不是"所有模型的通用最优值"。
集中维护在这里，就是为了后续能用评测结果整体调整，而不是散落到各业务文件里。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from .logging_setup import get_logger
from .providers import KNOWN_TEMPERATURE_MODELS, get_provider

# 能力判定的三种结果。
# 三态而不是布尔：把"没验证过"和"明确不支持"混成一个 False，
# 会让一个从没测过的模型被当成"不支持"，凭空少一个参数。
SUPPORTED = "supported"
UNSUPPORTED = "unsupported"
UNKNOWN = "unknown"

log = get_logger("llm.sampling")

# ---------------------------------------------------------------------------
# 策略表：用途 → 初始温度
# ---------------------------------------------------------------------------

# 未识别用途时的兜底。选 0.4 而不是 0.7：教学内容的默认诉求是"稳定、可复用"，
# 宁可保守一点，也不要让默认的教案/PPT 内容飘。
DEFAULT_TEMPERATURE = 0.4

PURPOSE_POLICY: Dict[str, float] = {
    # ---- 意图提取 / 结构化字段提取：要的是稳定复现，不是创意 ----
    "intent_extract": 0.1,
    "structured_extract": 0.1,
    "field_extract": 0.1,
    # ---- 知识问答 / 基于资料的解释 / 答案解析 ----
    "knowledge_qa": 0.2,
    "explanation": 0.2,
    "answer_analysis": 0.2,
    "lesson_qa": 0.2,
    # ---- 教案正文 / 课件内容组织 ----
    "lesson_plan_content": 0.4,
    "courseware_content": 0.4,
    "ppt_content": 0.4,
    "teaching_blueprint": 0.4,
    "topic_expansion": 0.4,
    "document_summary": 0.4,
    # ---- 课堂导入 / 活动方案 / 游戏玩法构思：需要发散 ----
    "lesson_intro": 0.7,
    "activity_design": 0.7,
    "gameplay_ideation": 0.7,
    # ---- 动画与游戏**代码**生成：要的是能跑、结构稳定 ----
    "animation_code": 0.2,
    "game_code": 0.2,
    "code_generation": 0.2,
    # ---- 通用对话（未细分的临时提问）----
    "chat": 0.4,
}

# 同一用途在不同执行阶段可以有不同的策略。
# 例如动画任务：先构思（发散）再写代码（确定）。
# 只有**现有流程本来就分了阶段**时才用得上；不要为了调温度去拆工作流。
STAGE_POLICY: Dict[Tuple[str, str], float] = {
    ("animation", "ideation"): 0.7,
    ("animation", "code"): 0.2,
    ("game", "ideation"): 0.7,
    ("game", "code"): 0.2,
    ("lesson_plan", "ideation"): 0.7,
    ("lesson_plan", "content"): 0.4,
}

# 这些用途在调用点**已经明确指定**了温度（规划 / 参数修复 / 验证 / 代码修复）。
# 它们属于内部约定，优先级高于任何全局设置 —— 普通手动值不得覆盖。
INTERNAL_EXPLICIT_PURPOSES = frozenset({
    "planner", "fix_tool_args", "verifier", "code_fix", "validation", "repair",
})

# ---------------------------------------------------------------------------
# 解析结果
# ---------------------------------------------------------------------------


@dataclass
class SamplingDecision:
    """一次采样参数的解析结果。

    带上 reason / source 是为了**可追踪**：出问题时能回答
    "这个值是从哪来的、为什么没发出去"，而不是靠猜。
    """

    purpose: str = ""
    stage: str = ""
    mode: str = "auto"                 # auto | manual
    policy: Optional[float] = None     # 策略表解析出的值（自动模式下）
    value: Optional[float] = None      # 最终解析值（可能因模型能力被调整为 None）
    sent: bool = False                 # 是否真的把 temperature 发给模型
    source: str = "policy"             # explicit | manual | policy | default | unsupported
    # 模型能力：supported | unsupported | unknown
    capability: str = SUPPORTED
    # 该能力是自动判定的，还是开发者选项里手动指定的
    capability_origin: str = "auto"    # auto | override
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "purpose": self.purpose,
            "stage": self.stage,
            "mode": self.mode,
            "policy": self.policy,
            "value": self.value,
            "sent": self.sent,
            "source": self.source,
            "capability": self.capability,
            "capability_origin": self.capability_origin,
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# 配置读取
# ---------------------------------------------------------------------------

AUTO = "auto"
MANUAL = "manual"


def read_sampling_mode(cfg: Optional[Dict[str, Any]]) -> str:
    """读取采样模式。**旧配置没有 samplingMode 时一律按自动模式处理** ——

    这一条是兼容性的核心：老用户只存了 temperature、没有模式字段，
    若按"有值就是手动"来推断，那份历史 0.7 就会继续覆盖所有自动策略，
    等于这次改造白做。
    """
    mode = str((cfg or {}).get("samplingMode") or "").strip().lower()
    return MANUAL if mode == MANUAL else AUTO


def read_manual_temperature(cfg: Optional[Dict[str, Any]]) -> Optional[float]:
    """读取手动值。

    ⚠️ 必须用 `is not None` 判断，**不能写 `cfg.get("temperature") or 0.7`**：
    那样会把合法的 0（"完全确定性"是教师可能想要的效果）悄悄换成 0.7。
    """
    raw = (cfg or {}).get("temperature")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# 模型能力适配（集中维护，禁止在业务文件里散落模型名判断）
# ---------------------------------------------------------------------------


def read_capability_override(cfg: Optional[Dict[str, Any]]) -> str:
    """读取开发者选项里的**能力手动覆盖**。

    为什么需要它：`local`（Ollama / vLLM / LMDeploy）和 `demo` 的模型名是
    用户自己填的，也可能是自建网关的私有命名 —— 清单里必然查不到，
    永远落在 unknown。给一个手动开关，让部署方自己确认后钉死，
    而不是让系统猜。
    """
    v = str((cfg or {}).get("temperatureOverride") or "").strip().lower()
    return v if v in (SUPPORTED, UNSUPPORTED) else "auto"


def model_temperature_state(
    provider: Optional[str],
    model: Optional[str],
    override: str = "auto",
) -> str:
    """该模型对 temperature 的能力：`supported` / `unsupported` / `unknown`。

    判定顺序：
      0. 开发者选项手动覆盖（supported / unsupported）→ 直接采用；
      1. 厂商级整包关闭 → unsupported；
      2. 命中"已知不接受"的模型名片段 → unsupported；
      3. 在项目实际使用/演示的清单里 → supported；
      4. 其余一律 **unknown** —— 保持兼容模式（照常发送），绝不编造它的能力。
    """
    if override in (SUPPORTED, UNSUPPORTED):
        return override
    spec = get_provider(provider)
    if not getattr(spec, "supports_temperature", True):
        return UNSUPPORTED
    name = str(model or "").lower()
    for pat in getattr(spec, "temperature_unsupported_patterns", ()) or ():
        if pat and pat in name:
            return UNSUPPORTED
    if (str(provider or "").lower(), name) in KNOWN_TEMPERATURE_MODELS:
        return SUPPORTED
    return UNKNOWN


def model_supports_temperature(
    provider: Optional[str],
    model: Optional[str],
    override: str = "auto",
) -> bool:
    """是否**发送** temperature。

    注意与"能力"区分：unknown 也照常发送（兼容模式），
    只有明确 unsupported 才不发 —— 否则一个没验证过的模型会被凭空砍掉参数。

    `override` 必须与 `model_temperature_state` 一致地透传：
    两边不一致会出现"能力显示不支持、实际照样发参数"这种最坏情况。
    """
    return model_temperature_state(provider, model, override) != UNSUPPORTED


def clamp_temperature(provider: Optional[str], value: float) -> float:
    """按厂商声明的取值区间收敛。超出区间就取边界，而不是照发导致 400。"""
    spec = get_provider(provider)
    lo, hi = getattr(spec, "temperature_range", (0.0, 2.0)) or (0.0, 2.0)
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


# ---------------------------------------------------------------------------
# 策略解析
# ---------------------------------------------------------------------------


def policy_for(purpose: str, stage: str = "") -> Tuple[Optional[float], str]:
    """查策略表。

    优先用（用途 + 阶段）的组合，其次只用用途。
    查不到时返回 None —— 由调用方决定是"保留显式值"还是"用兜底默认值"。
    """
    if stage:
        hit = STAGE_POLICY.get((purpose, stage))
        if hit is not None:
            return hit, f"命中阶段策略 {purpose}/{stage}"
    hit = PURPOSE_POLICY.get(purpose)
    if hit is not None:
        return hit, f"命中用途策略 {purpose}"
    return None, ""


def resolve_temperature(
    *,
    purpose: str = "chat",
    stage: str = "",
    explicit: Optional[float] = None,
    config: Optional[Dict[str, Any]] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> SamplingDecision:
    """解析本次请求最终使用的 temperature。

    优先级（从高到低）：
      1. **调用点明确指定**（内部约定：规划 / 参数修复 / 验证 / 代码修复）
         —— 全局手动设置不得覆盖；
      2. 手动模式下的合法手动值；
      3. 用途 / 阶段策略；
      4. 兜底默认值。
    最后统一过一遍**模型能力**：不支持就不发这个参数（而不是发了被 400 打回）。
    """
    d = SamplingDecision(purpose=purpose or "chat", stage=stage or "")
    d.mode = read_sampling_mode(config)
    # 能力覆盖来自开发者选项（local / demo / 自定义模型用它钉死结论）
    override = read_capability_override(config)
    d.capability_origin = "override" if override != "auto" else "auto"

    # ---- 1. 调用点明确指定 ------------------------------------------------
    # 用 `is not None` 而不是 `if explicit` —— 0.0 是合法且常用的值（完全确定）。
    if explicit is not None:
        try:
            val = float(explicit)
        except (TypeError, ValueError):
            val = DEFAULT_TEMPERATURE
            d.reason = "显式值无法解析，已回退默认策略"
        else:
            d.reason = "调用点明确指定（内部约定，优先于全局设置）"
        d.value = val
        d.source = "explicit"
        d.policy = val
        _apply_capability(d, provider, model, override)
        return d

    # ---- 2. 手动模式 ------------------------------------------------------
    if d.mode == MANUAL:
        manual = read_manual_temperature(config)
        if manual is None:
            d.reason = "手动模式但未填数值，回退自动策略"
        else:
            lo, hi = getattr(get_provider(provider), "temperature_range", (0.0, 2.0)) or (0.0, 2.0)
            if manual < lo or manual > hi:
                d.reason = f"手动值 {manual} 超出该模型区间 [{lo}, {hi}]，回退自动策略"
            else:
                d.value = manual
                d.policy = manual
                d.source = "manual"
                d.reason = "手动模式：使用设置页填写的值"
                _apply_capability(d, provider, model, override)
                return d

    # ---- 3. 用途 / 阶段策略 ----------------------------------------------
    policy, why = policy_for(d.purpose, d.stage)
    if policy is None:
        policy = DEFAULT_TEMPERATURE
        d.reason = (d.reason + "；" if d.reason else "") + "未识别用途，使用默认策略"
    else:
        d.reason = (d.reason + "；" if d.reason else "") + why
    d.policy = policy
    d.value = policy
    d.source = "policy" if why else "default"
    _apply_capability(d, provider, model, override)
    return d


def _apply_capability(
    d: SamplingDecision,
    provider: Optional[str],
    model: Optional[str],
    override: str = "auto",
) -> None:
    """最后一道闸门：模型不接受 temperature 就不发，而不是发了再被拒绝。

    只在这里判断"能力"，**不在这里处理错误重试** ——
    把鉴权 / 限流 / 网络错误误判成"温度不支持"会造成更糟的后果。
    """
    state = model_temperature_state(provider, model, override)
    d.capability = state

    if state == UNSUPPORTED:
        # 只在这里做**能力预判并省略参数**。刻意不新增"报错后重试"：
        # 把鉴权 / 限流 / 网络错误误判成"温度不支持"会造成更糟的后果。
        d.sent = False
        d.value = None
        d.source = "unsupported"
        d.reason = f"模型 {model or '未知'} 不接受 temperature，按厂商默认行为发送"
        return

    if state == UNKNOWN:
        # 兼容模式：照常发送，但把"没验证过"如实记进追踪，不假装确认过能力
        d.reason += "；该模型不在已验证清单内，按兼容模式发送（无法确认参数是否生效）"
    elif d.capability_origin == "override":
        d.reason += f"；能力由开发者选项手动指定为 {state}"

    if d.value is None:
        d.sent = False
        return
    clamped = clamp_temperature(provider, d.value)
    if abs(clamped - d.value) > 1e-9:
        d.reason += f"；超出模型区间，已收敛为 {clamped}"
        d.value = clamped
    d.sent = True


def describe(decision: SamplingDecision) -> str:
    """给日志用的一句话描述。不含密钥、不含用户正文。"""
    if not decision.sent:
        return f"[sampling] {decision.purpose}/{decision.stage or '-'} 未发送 temperature（{decision.reason}）"
    return (
        f"[sampling] {decision.purpose}/{decision.stage or '-'} mode={decision.mode} "
        f"source={decision.source} 策略值={decision.policy} 发送值={decision.value}（{decision.reason}）"
    )
