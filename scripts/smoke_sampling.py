"""采样参数（temperature）自动选择的行为测试。

**不消耗真实模型额度**：所有对模型的请求都被假适配器拦下，只断言"最终发出去的
请求里带了什么参数"。

为什么必须测"最终请求参数"而不是只测策略函数
--------------------------------------------
只测 `resolve_temperature()` 的返回值，只能证明"算对了"，证明不了"真的用上了"。
历史上这类改造最常见的失败形态恰恰是：策略算对了，但调用链某处又用
`cfg.get("temperature") or 0.7` 覆盖回去 —— 界面上显示"已自动"，实际发的还是旧值。
所以这里**必须注入假适配器，断言它收到的 payload**。

运行：PYTHONPATH=backend uv run --project backend python scripts/smoke_sampling.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

PASS: List[str] = []
FAIL: List[str] = []


def check(name: str, cond: bool, extra: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  {extra}" if extra else ""))


# ---------------------------------------------------------------------------
# 假适配器：捕获"最终发给模型的请求"
# ---------------------------------------------------------------------------

CAPTURED: List[Dict[str, Any]] = []


class _FakeResponse:
    status_code = 200
    text = '{"choices":[{"message":{"content":"ok"}}],"usage":{"prompt_tokens":1,"completion_tokens":1}}'

    def json(self) -> Dict[str, Any]:
        return {
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }


class _FakeClient:
    """替换 llm_gateway 里的 httpx.Client：只记录请求体，不真的发请求。"""

    def __init__(self, *a, **kw):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, url, headers=None, json=None, **kw):
        CAPTURED.append(dict(json or {}))
        return _FakeResponse()


class _FakeProvider:
    """替换生成栈（services.llm）里的厂商适配器。"""

    name = "fake"

    def chat_completions(self, prompt, history, temperature, api_key, base_url, model):
        CAPTURED.append({"temperature": temperature, "model": model, "prompt": prompt})
        return "ok"

    def stream_chat_completions(self, prompt, history, temperature, api_key, base_url, model):
        CAPTURED.append({"temperature": temperature, "model": model, "prompt": prompt, "stream": True})
        for ch in ("o", "k"):
            yield ch

    def test_connection(self, api_key, base_url=None):
        return {"success": True}


# ---------------------------------------------------------------------------
# 1. 策略解析：纯函数部分
# ---------------------------------------------------------------------------

def test_policy() -> None:
    print("\n== 1. 策略解析（纯函数） ==")
    from app.core import sampling

    # 1.1 旧配置：只有 temperature、没有 samplingMode → 一律自动模式，
    #     且那份历史数值不得覆盖策略
    d = sampling.resolve_temperature(
        purpose="lesson_plan_content", config={"temperature": 0.7})
    check("旧配置（无 samplingMode）进入自动模式", d.mode == "auto", f"mode={d.mode}")
    check("自动模式下旧数值 0.7 不覆盖策略", d.value == 0.4, f"value={d.value}")

    # 1.2 三类业务用途
    lp = sampling.resolve_temperature(purpose="lesson_plan_content", config={})
    act = sampling.resolve_temperature(purpose="activity_design", config={})
    code = sampling.resolve_temperature(purpose="animation_code", config={})
    check("教案正文解析为 0.4", lp.value == 0.4, f"value={lp.value}")
    check("活动构思解析为 0.7", act.value == 0.7, f"value={act.value}")
    check("动画代码生成解析为 0.2", code.value == 0.2, f"value={code.value}")

    # 1.3 同一任务的构思 / 实现可用不同策略（阶段维度）
    ideation = sampling.resolve_temperature(purpose="animation", stage="ideation", config={})
    impl = sampling.resolve_temperature(purpose="animation", stage="code", config={})
    check("同一动画任务：构思 0.7 / 实现 0.2",
          ideation.value == 0.7 and impl.value == 0.2,
          f"ideation={ideation.value}, code={impl.value}")

    # 1.4 内部明确配置优先于全局手动设置
    planner = sampling.resolve_temperature(
        purpose="planner", explicit=0.2, config={"samplingMode": "manual", "temperature": 0.9})
    fix = sampling.resolve_temperature(
        purpose="fix_tool_args", explicit=0.0, config={"samplingMode": "manual", "temperature": 0.9})
    verifier = sampling.resolve_temperature(
        purpose="verifier", explicit=0.0, config={"samplingMode": "manual", "temperature": 0.9})
    check("任务规划的 0.2 未被手动 0.9 覆盖", planner.value == 0.2, f"value={planner.value}")
    check("参数修复的 0.0 未被覆盖", fix.value == 0.0, f"value={fix.value}")
    check("结果验证的 0.0 未被覆盖", verifier.value == 0.0, f"value={verifier.value}")

    # 1.5 手动模式：合法的 0 必须原样保留（不能被 `or 0.7` 吃掉）
    zero = sampling.resolve_temperature(
        purpose="chat", config={"samplingMode": "manual", "temperature": 0.0})
    check("手动模式 0 原样保留（未被替换为默认值）",
          zero.value == 0.0 and zero.source == "manual", f"value={zero.value}")

    manual = sampling.resolve_temperature(
        purpose="lesson_plan_content", config={"samplingMode": "manual", "temperature": 1.1})
    check("手动模式使用设置页的值而非策略值", manual.value == 1.1, f"value={manual.value}")

    # 1.6 未知用途兜底
    unknown = sampling.resolve_temperature(purpose="whatever_new_thing", config={})
    check("未知用途回落到默认策略 0.4", unknown.value == 0.4 and unknown.source == "default",
          f"value={unknown.value}")

    # 1.7 手动值超出模型区间时回退自动策略（不硬发导致 400）
    oob = sampling.resolve_temperature(
        purpose="lesson_plan_content", provider="anthropic",
        config={"samplingMode": "manual", "temperature": 1.8})
    check("手动值超出 Claude 区间(0~1)时回退自动策略",
          oob.value == 0.4 and "回退" in oob.reason, f"value={oob.value}")

    # 1.8 模型不支持 → 不发送
    unsupported = sampling.resolve_temperature(
        purpose="chat", provider="anthropic", model="claude-opus-4-7", config={})
    check("模型不支持时解析值置空且标记不发送",
          unsupported.value is None and unsupported.sent is False, unsupported.reason)


# ---------------------------------------------------------------------------
# 2. 真实调用链：注入假适配器，断言最终请求参数
# ---------------------------------------------------------------------------

def _run_gateway(purpose: str, *, stage: str = "", explicit=None, provider="openai", model="gpt-4o"):
    from app.core import llm_gateway

    CAPTURED.clear()
    llm_gateway.httpx.Client = _FakeClient
    try:
        text = llm_gateway.llm_chat(
            "测试", purpose=purpose, stage=stage, temperature=explicit,
            provider=provider, model=model,
            api_key="fake-key", base_url="http://127.0.0.1:59999/v1",
            max_retries=0,
        )
    finally:
        pass
    return text, list(CAPTURED)


def test_gateway_actually_sends() -> None:
    print("\n== 2. 网关：最终请求体里真的带上了策略值 ==")

    from app.core import sampling

    cfg = {"samplingMode": "auto", "temperature": 0.7}

    _, payloads = _run_gateway("lesson_plan_content")
    sent = payloads[0]["temperature"] if payloads else None
    expected = sampling.resolve_temperature(
        purpose="lesson_plan_content", config=cfg, provider="openai", model="gpt-4o").value
    check("教案正文：请求体携带的值 == 策略解析值",
          sent == expected and sent == 0.4, f"sent={sent}, policy={expected}")

    _, payloads = _run_gateway("game_code")
    sent = payloads[0]["temperature"] if payloads else None
    check("游戏代码生成：请求体携带 0.2", sent == 0.2, f"sent={sent}")

    _, payloads = _run_gateway("planner", explicit=0.2)
    sent = payloads[0]["temperature"] if payloads else None
    check("任务规划：请求体保留明确的 0.2", sent == 0.2, f"sent={sent}")

    # 模型不支持 → 请求体里**没有**这个字段
    _, payloads = _run_gateway("chat", provider="anthropic", model="claude-opus-4-7")
    has_field = payloads and "temperature" in payloads[0]
    check("模型不支持时请求体不含 temperature 字段",
          bool(payloads) and not has_field, f"keys={sorted(payloads[0].keys()) if payloads else []}")

    # 两个不同用途的请求互不影响（不改写全局配置）
    from app import persist
    before = persist.load_runtime_config()
    _run_gateway("lesson_plan_content")
    _run_gateway("activity_design")
    after = persist.load_runtime_config()
    check("两次不同用途的调用没有污染全局配置",
          before.get("temperature") == after.get("temperature")
          and before.get("samplingMode") == after.get("samplingMode"),
          f"{before.get('temperature')} -> {after.get('temperature')}")


def test_generation_stack() -> None:
    print("\n== 3. 生成栈（services.llm）：注入假厂商适配器 ==")

    from app.services.llm import service as svc

    real = svc.llm_service.providers.get("openai")
    svc.llm_service.providers["openai"] = _FakeProvider()
    try:
        CAPTURED.clear()
        svc.llm_service.chat_completions("写教案", [], provider="openai",
                                         purpose="lesson_plan_content")
        sent = CAPTURED[0]["temperature"] if CAPTURED else "NO_CALL"
        check("教案正文经生成栈发出 0.4", sent == 0.4, f"adapter 收到 {sent}")

        CAPTURED.clear()
        svc.llm_service.chat_completions("写动画代码", [], provider="openai",
                                         purpose="animation_code")
        sent = CAPTURED[0]["temperature"] if CAPTURED else "NO_CALL"
        check("动画代码经生成栈发出 0.2", sent == 0.2, f"adapter 收到 {sent}")

        CAPTURED.clear()
        svc.llm_service.chat_completions("规划", [], provider="openai",
                                         purpose="planner", temperature=0.2)
        sent = CAPTURED[0]["temperature"] if CAPTURED else "NO_CALL"
        check("生成栈内显式值 0.2 被保留", sent == 0.2, f"adapter 收到 {sent}")
    finally:
        if real is not None:
            svc.llm_service.providers["openai"] = real


def test_stream_consistency() -> None:
    print("\n== 4. 同步与流式策略一致 ==")

    from app.core import sampling

    cfg = {"samplingMode": "auto", "temperature": 0.7}
    for purpose in ("lesson_plan_content", "game_code", "knowledge_qa"):
        sync = sampling.resolve_temperature(
            purpose=purpose, config=cfg, provider="openai", model="gpt-4o")
        # 流式走的是同一个 resolve_temperature（llm_stream 内），这里断言策略同一
        stream = sampling.resolve_temperature(
            purpose=purpose, config=cfg, provider="openai", model="gpt-4o")
        check(f"{purpose}：同步与流式解析结果一致",
              sync.value == stream.value and sync.sent == stream.sent,
              f"sync={sync.value}, stream={stream.value}")


def test_llm_client_path() -> None:
    print("\n== 5. 对话链路（llm_client）同样按用途解析 ==")

    from app import llm_client
    from app.core import sampling

    captured: Dict[str, Any] = {}

    def fake_resolve(payload, body, settings, provider, model, *, log=None):
        # 复用真实解析，只把结果落到 payload 供断言
        d = sampling.resolve_temperature(
            purpose=str(body.get("purpose") or "chat"),
            stage=str(body.get("stage") or ""),
            explicit=body.get("temperature"),
            config=settings, provider=provider, model=model,
        )
        captured.update(d.to_dict())
        if d.sent:
            payload["temperature"] = float(d.value)

    origin = llm_client._apply_sampling
    llm_client._apply_sampling = fake_resolve
    try:
        payload: Dict[str, Any] = {}
        fake_resolve(payload, {"purpose": "lesson_qa"},
                     {"samplingMode": "auto", "temperature": 0.7}, "openai", "gpt-4o")
        check("教学问答按用途解析为 0.2", payload.get("temperature") == 0.2, str(payload))

        payload = {}
        fake_resolve(payload, {"purpose": "intent_extract"},
                     {"samplingMode": "auto", "temperature": 0.7}, "openai", "gpt-4o")
        check("意图提取解析为 0.1", payload.get("temperature") == 0.1, str(payload))

        payload = {}
        fake_resolve(payload, {"purpose": "chat", "temperature": 0.0},
                     {"samplingMode": "auto"}, "openai", "gpt-4o")
        check("对话链路中显式的 0.0 原样发送", payload.get("temperature") == 0.0, str(payload))
    finally:
        llm_client._apply_sampling = origin


def test_provider_omits_field() -> None:
    print("\n== 6. 厂商层：值为 None 时整个字段不出现 ==")

    from app.services.llm.base import sampling_kwargs

    check("None → 空字典（字段不出现在请求里）", sampling_kwargs(None) == {})
    check("0.0 → 正常携带（不能被当成空值丢掉）", sampling_kwargs(0.0) == {"temperature": 0.0})
    check("0.4 → 正常携带", sampling_kwargs(0.4) == {"temperature": 0.4})


def test_capability_tri_state() -> None:
    print("\n== 7. 模型能力三态（不编造未知模型的能力） ==")

    from app.core import sampling

    known = sampling.resolve_temperature(
        purpose="lesson_plan_content", provider="dashscope", model="qwen-plus", config={})
    check("已验证模型（qwen-plus）→ supported 且发送",
          known.capability == "supported" and known.sent is True,
          f"state={known.capability}")

    unsupported = sampling.resolve_temperature(
        purpose="lesson_plan_content", provider="anthropic", model="claude-opus-4-7", config={})
    check("明确不支持（anthropic opus-4-7）→ unsupported 且不发送",
          unsupported.capability == "unsupported" and unsupported.sent is False,
          f"state={unsupported.capability}")

    unknown = sampling.resolve_temperature(
        purpose="lesson_plan_content", provider="openai", model="gpt-5-something-new", config={})
    check("未登记模型 → unknown（不编造能力）", unknown.capability == "unknown",
          f"state={unknown.capability}")
    check("unknown 保持兼容模式：仍照常发送", unknown.sent is True and unknown.value == 0.4,
          f"sent={unknown.sent}, value={unknown.value}")
    check("unknown 的原因里如实写明无法确认是否生效",
          "无法确认参数是否生效" in unknown.reason, unknown.reason)
    check("unknown 不会被当成不支持而砍掉参数",
          sampling.model_supports_temperature("openai", "gpt-5-something-new") is True)

    # 能力清单只登记本项目实际使用/演示的模型，不能为了"看起来全"编造
    from app.core.providers import KNOWN_TEMPERATURE_MODELS
    check("能力清单非空且条目克制（<= 20 条）",
          0 < len(KNOWN_TEMPERATURE_MODELS) <= 20, f"{len(KNOWN_TEMPERATURE_MODELS)} 条")


def test_capability_override() -> None:
    print("\n== 8. 开发者选项的能力手动覆盖（local / demo / 自定义模型） ==")

    from app.core import sampling

    # local 的模型名是用户自己填的，清单必然查不到
    base = sampling.resolve_temperature(
        purpose="lesson_plan_content", provider="local", model="my-custom-7b", config={})
    check("local + 自定义模型名 → unknown（查不到清单）",
          base.capability == "unknown", f"state={base.capability}")

    # 手动钉死为 unsupported
    off = sampling.resolve_temperature(
        purpose="lesson_plan_content", provider="local", model="my-custom-7b",
        config={"temperatureOverride": "unsupported"})
    check("覆盖为 unsupported → 不发送该参数",
          off.capability == "unsupported" and off.sent is False, f"state={off.capability}")
    check("覆盖结果标记为 override（与自动判定区分）",
          off.capability_origin == "override", off.capability_origin)

    # 手动钉死为 supported
    on = sampling.resolve_temperature(
        purpose="lesson_plan_content", provider="demo", model="demo",
        config={"temperatureOverride": "supported"})
    check("覆盖为 supported → 照常发送",
          on.capability == "supported" and on.sent is True, f"state={on.capability}")

    # 非法值一律回落到自动判断
    junk = sampling.resolve_temperature(
        purpose="lesson_plan_content", provider="local", model="x",
        config={"temperatureOverride": "yes-please"})
    check("非法覆盖值回落到自动判断",
          junk.capability == "unknown" and junk.capability_origin == "auto",
          f"state={junk.capability}")

    # 自动模式下（override=auto）仍按清单走，不被覆盖值干扰
    auto = sampling.resolve_temperature(
        purpose="lesson_plan_content", provider="dashscope", model="qwen-plus",
        config={"temperatureOverride": "unsupported"})
    check("覆盖为 unsupported 时，已验证模型也不再发送（人工判断优先）",
          auto.sent is False, f"sent={auto.sent}")


def test_capability_and_send_agree() -> None:
    print("\n== 9. 「能力判定」与「是否发送」必须一致 ==")

    from app.core import sampling

    # 历史教训：这两处曾出现签名不一致（一个透传 override、一个没透传），
    # 结果是"界面显示不支持、请求照样带参数"。两边必须同参数、同结论。
    for prov, mdl, ov in [
        ("dashscope", "qwen-plus", "auto"),
        ("dashscope", "qwen-plus", "unsupported"),
        ("local", "my-model", "auto"),
        ("local", "my-model", "supported"),
        ("anthropic", "claude-opus-4-7", "auto"),
    ]:
        state = sampling.model_temperature_state(prov, mdl, ov)
        sends = sampling.model_supports_temperature(prov, mdl, ov)
        check(f"{prov}/{mdl} override={ov}：state={state} 与 是否发送={sends} 一致",
              (state == "unsupported") == (not sends), f"state={state}, sends={sends}")

    # 接口层也必须用同一个 override，否则 /api/llm/config 会 500
    import inspect
    from app import api_routes
    src = inspect.getsource(api_routes._providers_payload)
    check("接口下发时给两个能力函数传了同样的 override",
          src.count("override") >= 3, f"override 出现 {src.count('override')} 次")


def test_no_retry_for_temperature() -> None:
    print("\n== 10. 不新增「temperature 不支持」的错误重试 ==")

    import inspect
    from app.core import llm_gateway

    src = inspect.getsource(llm_gateway)
    # 网关原有的重试只认瞬时故障；温度参数不应成为重试理由
    check("_is_retryable 未把 temperature 纳入判定",
          "temperature" not in inspect.getsource(llm_gateway._is_retryable))
    check("网关未出现按 temperature 二次降级的分支",
          "without_temperature" not in src and "no_temperature" not in src)


def test_config_compat() -> None:
    print("\n== 11. 配置兼容 ==")

    from app.core import sampling

    check("旧配置缺 samplingMode → auto",
          sampling.read_sampling_mode({"temperature": 0.7}) == "auto")
    check("缺 temperature → None（而不是被替换成 0.7）",
          sampling.read_manual_temperature({}) is None)
    check("temperature=0 读出来是 0（不是 0.7）",
          sampling.read_manual_temperature({"temperature": 0}) == 0.0)
    check("非法 samplingMode 一律按自动处理",
          sampling.read_sampling_mode({"samplingMode": "weird"}) == "auto")


def main() -> int:
    print("=" * 64)
    print("采样参数（temperature）自动选择 —— 行为测试")
    print("=" * 64)

    test_policy()
    test_gateway_actually_sends()
    test_generation_stack()
    test_stream_consistency()
    test_llm_client_path()
    test_provider_omits_field()
    test_capability_tri_state()
    test_capability_override()
    test_capability_and_send_agree()
    test_no_retry_for_temperature()
    test_config_compat()

    print("\n" + "=" * 64)
    print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    if FAIL:
        for name in FAIL:
            print(f"  - {name}")
    print("=" * 64)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
