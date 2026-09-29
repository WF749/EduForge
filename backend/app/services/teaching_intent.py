"""教学意图（TeachingIntent）—— 这一节课"要教成什么样"的结构化描述。

⚠️ 命名必须看清：本模块的"教学意图"与 `services/intent_service.py` 的"意图"
**不是一回事**：

  * `intent_service.IntentService` 的 intent = **通用对话意图**
    （用户想让系统做什么：生成教案 / 提问 / 修改），字段是
    `intent_type` + `extracted_fields` + `missing_fields`；
  * 本模块的 `TeachingIntent` = **这一节课的教学设计意图**
    （教学目标、知识点、重难点、教学方法、互动形式…）。

两者同名会在代码里分不清谁是谁，因此这里一律用 `teaching_intent` / `TeachingIntent`
全称，台账字段也用全称。

设计约束（与既有代码兼容）
--------------------------
1. **只复用不另立**：topic / subject / grade / duration / difficulty 仍然是
   `store/lesson.js` 与 `lesson_tutor.build_lesson_context()` 读的那几个扁平字段；
   TeachingIntent 是它们的**视图 + 扩展**，不是另一份副本 —— 否则问答语境会丢。
2. **学段沿用后端既有取值**（`llm_lesson_plan_all_stages` 的 level_rules 键名）：
   小学 / 初中 / 普通高中 / 职业高中·中等职业学校 / 普通高等院校。
   不自造"高中"，这样 `stage` 可直接喂给 `analyze_requirements(level=...)`，零转换。
3. **能识别就提取，识别不了就留空**：所有新增字段缺省为空数组/空串，
   绝不为了填满字段而编造（编造的难点会让整份教案跑偏）。
4. **不存正文**：这里只有结构化小字段，长度一律封顶，任务台账不会被撑大。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

__all__ = [
    "LEVELS", "TeachingIntent", "KEY_FIELDS", "CORE_KEYS",
    "stage_for_grade", "normalize_teaching_intent", "missing_key_fields",
    "intent_to_prompt_text", "sync_intent_with_flat",
]

# 与扁平课程字段共享真值的字段。**扁平字段是真值，意图里的这几项是镜像** ——
# 否则教师在工作台改主题后，意图里还留着旧主题，同一节课就有两个主题。
CORE_KEYS = ("topic", "subject", "grade", "duration", "difficulty")

# 学段取值 —— 与 llm_lesson_plan_all_stages 的 level_rules 键名保持一致
LEVELS = ("小学", "初中", "普通高中", "职业高中·中等职业学校", "普通高等院校")

# 与前端 GRADES 一致的年级前缀判定
_PRIMARY = re.compile(r"^[一二三四五六]年级$")
_JUNIOR = re.compile(r"^[七八九]年级$")
_SENIOR = re.compile(r"^高[一二三]$")

# 长度封顶：台账里只放结构化信息，不放正文
_MAX_ITEMS = 12          # 每个列表最多几条
_MAX_ITEM = 200          # 每条最多多少字
_MAX_TEXT = 500          # 自由文本字段最多多少字


def _safe_int(v: Any, default: int = 0) -> int:
    """脏数据不能让"宽容解析"变成真的抛异常：时间字段来自模型与前端，
    "abc"、None、嵌套结构都出现过。"""
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, str):
        try:
            return int(float(v.strip()))
        except (TypeError, ValueError):
            return default
    return default


def _clean(v: Any, limit: int = _MAX_TEXT) -> str:
    """转成字符串并去空白、封顶。None / 非字符串一律变成空串而不是 'None'。"""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "是" if v else "否"
    if isinstance(v, (int, float)):
        return str(v)
    if not isinstance(v, str):
        return ""
    return re.sub(r"\s+", " ", v).strip()[:limit]


def _clean_list(v: Any) -> List[str]:
    """整理成字符串列表：过滤空项、去重、封顶。非列表一律按空列表处理。"""
    if v is None:
        return []
    if isinstance(v, str):
        items = re.split(r"[；;\n]+", v)
    elif isinstance(v, (list, tuple, set)):
        items = list(v)
    else:
        return []
    out: List[str] = []
    for it in items:
        s = _clean(it, _MAX_ITEM)
        if s and s not in out:
            out.append(s)
        if len(out) >= _MAX_ITEMS:
            break
    return out


def stage_for_grade(grade: Any, stage: Any = "") -> str:
    """由年级推导学段；已给出学段则优先沿用（并归一到既有取值）。

    "高中语文"这类输入认得出学段、认不出具体年级 —— 所以 stage 是独立字段，
    不能只靠 grade 推。推导不出来就返回空串（不猜）。
    """
    given = _clean(stage, 20)
    if given:
        for lv in LEVELS:
            if lv in given or given in lv:
                return lv
        if "高中" in given or "高一" in given or "高二" in given or "高三" in given:
            return "普通高中"
        if "职" in given or "中专" in given:
            return "职业高中·中等职业学校"
        if "大学" in given or "高校" in given:
            return "普通高等院校"
    g = _clean(grade, 20)
    if _PRIMARY.match(g):
        return "小学"
    if _JUNIOR.match(g):
        return "初中"
    if _SENIOR.match(g):
        return "普通高中"
    return ""


@dataclass
class TeachingIntent:
    """一节课的教学设计意图。

    所有字段都有默认值 —— 老数据缺任意字段都能安全构造，不会 KeyError。
    """
    # ── 复用现有扁平字段（与 store / lesson_tutor 同一套名字）──
    topic: str = ""
    subject: str = ""
    grade: str = ""
    stage: str = ""
    duration: int = 45
    difficulty: str = "medium"

    # ── 新增：教学意图（缺省皆空，绝不编造）──
    goals: List[str] = field(default_factory=list)              # 教学目标
    knowledgePoints: List[str] = field(default_factory=list)    # 知识点
    focusPoints: List[str] = field(default_factory=list)        # 教学重点
    hardPoints: List[str] = field(default_factory=list)         # 教学难点
    methods: List[str] = field(default_factory=list)            # 教学方法
    interactions: List[str] = field(default_factory=list)       # 互动形式
    artifactKinds: List[str] = field(default_factory=list)      # 期望产物
    stylePreference: str = ""
    learnerNote: str = ""
    constraints: str = ""

    # ── 元信息：`filled` 是"已识别的不重问"的依据 ──
    filled: Dict[str, str] = field(default_factory=dict)
    updatedAt: int = 0

    # 值得追问的关键字段（中文标签）。一次最多问一个。
    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic, "subject": self.subject, "grade": self.grade,
            "stage": self.stage, "duration": self.duration,
            "difficulty": self.difficulty,
            "goals": list(self.goals), "knowledgePoints": list(self.knowledgePoints),
            "focusPoints": list(self.focusPoints), "hardPoints": list(self.hardPoints),
            "methods": list(self.methods), "interactions": list(self.interactions),
            "artifactKinds": list(self.artifactKinds),
            "stylePreference": self.stylePreference,
            "learnerNote": self.learnerNote, "constraints": self.constraints,
            "filled": dict(self.filled), "updatedAt": self.updatedAt,
        }


# 关键字段：缺了会明显影响产物质量，才值得追问。
# 不把"教学方法""互动形式"这类放进来 —— 它们有合理默认值，问了反而烦。
KEY_FIELDS: Sequence[tuple] = (
    ("topic", "教学主题"),
    ("subject", "学科"),
    ("grade", "年级"),
    ("duration", "课时"),
    ("goals", "教学目标"),
    ("knowledgePoints", "知识点"),
)


def normalize_teaching_intent(
    payload: Any = None,
    *,
    base: Optional[Dict[str, Any]] = None,
    mark_auto: bool = True,
) -> TeachingIntent:
    """宽容解析：任何形状的输入都返回合法的 TeachingIntent。

    `base` 传入现有扁平课程字段（topic/subject/grade/duration/difficulty），
    保证与 store 和 lesson_tutor 读的是同一份值 —— 不另存副本。

    `mark_auto=True` 时，有值的字段会记进 `filled`，供"已识别的不重问"判定。
    """
    src: Dict[str, Any] = {}
    for d in (base or {}, payload if isinstance(payload, dict) else {}):
        if isinstance(d, dict):
            src.update(d)

    duration = _safe_int(src.get("duration"), 45)
    if duration <= 0:
        duration = 45
    # 与后端 lesson_tasks 的钳制保持一致（15–180）
    duration = max(15, min(180, duration))

    difficulty = _clean(src.get("difficulty"), 20) or "medium"
    if difficulty not in ("easy", "medium", "hard"):
        difficulty = "medium"

    intent = TeachingIntent(
        topic=_clean(src.get("topic"), _MAX_TEXT),
        subject=_clean(src.get("subject"), 40),
        grade=_clean(src.get("grade"), 20),
        stage=stage_for_grade(src.get("grade"), src.get("stage")),
        duration=duration,
        difficulty=difficulty,
        goals=_clean_list(src.get("goals")),
        knowledgePoints=_clean_list(src.get("knowledgePoints")),
        focusPoints=_clean_list(src.get("focusPoints")),
        hardPoints=_clean_list(src.get("hardPoints")),
        methods=_clean_list(src.get("methods")),
        interactions=_clean_list(src.get("interactions")),
        artifactKinds=_clean_list(src.get("artifactKinds")),
        stylePreference=_clean(src.get("stylePreference"), _MAX_TEXT),
        learnerNote=_clean(src.get("learnerNote"), _MAX_TEXT),
        constraints=_clean(src.get("constraints"), _MAX_TEXT),
        updatedAt=_safe_int(src.get("updatedAt"), 0),
    )

    if mark_auto:
        filled: Dict[str, str] = {}
        for key in ("topic", "subject", "grade", "stage", "goals",
                    "knowledgePoints", "focusPoints", "hardPoints",
                    "methods", "interactions", "artifactKinds"):
            val = getattr(intent, key)
            if val:
                filled[key] = _clean(src.get(f"{key}Source"), 10) or "auto"
        # 教师显式改过的保留原标记
        old = src.get("filled")
        if isinstance(old, dict):
            for k, v in old.items():
                if isinstance(v, str) and v in ("auto", "teacher"):
                    filled[k] = v
        intent.filled = filled
    return intent


def sync_intent_with_flat(
    intent: Any,
    flat: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """让教学意图与扁平课程字段收敛成**同一份真值**。

    为什么要这个函数
    ----------------
    两边都可能被改：教师在工作台顶部改主题（扁平字段），
    或在教学意图卡片里改（意图字段）。若只在保存意图时合并一次，
    之后只改扁平字段就不会同步已有意图 —— **同一节课出现两个主题**，
    后续生成到底依据哪一个是不确定的（这个 bug 不报错，只是悄悄跑偏）。

    规则（**扁平字段是真值**）：
      * 扁平字段有值 → 覆盖意图里的镜像字段；
      * 扁平字段为空而意图有值 → 补进扁平字段（首次从意图识别出来的情况）。

    `stage` 不在扁平侧，始终由 `grade` 派生。

    返回 `(intent_dict, flat_patch)`：flat_patch 是需要回写到课程上的字段。
    """
    if isinstance(intent, TeachingIntent):
        it = intent.to_dict()
    elif isinstance(intent, dict):
        it = dict(intent)
    else:
        it = {}

    flat = dict(flat or {})
    patch: Dict[str, Any] = {}

    for key in CORE_KEYS:
        fv, iv = flat.get(key), it.get(key)
        if key == "duration":
            fn = _safe_int(fv, 0)
            iv_n = _safe_int(iv, 0)
            if fn:
                it[key] = max(15, min(180, fn))
            elif iv_n:
                patch[key] = max(15, min(180, iv_n))
                it[key] = max(15, min(180, iv_n))
            continue
        fs = _clean(fv, _MAX_TEXT)
        isv = _clean(iv, _MAX_TEXT)
        if fs:
            it[key] = fs
        elif isv:
            patch[key] = isv
            it[key] = isv

    # 两侧都是脏数据时不能把原始脏值留在意图里：下游 int() 会炸，
    # 或更糟 —— 拿到一个非法的课时。这里统一收敛成合法值。
    if not _safe_int(it.get("duration"), 0):
        it["duration"] = max(15, min(180, _safe_int(flat.get("duration"), 45) or 45))

    it["stage"] = stage_for_grade(it.get("grade"), it.get("stage"))
    return it, patch


def missing_key_fields(intent: TeachingIntent) -> List[str]:
    """返回仍缺失的关键字段（中文标签）。

    调用方应当**一次最多问一个**，且只问这里返回的 —— 已识别的不重问。
    """
    missing: List[str] = []
    for key, label in KEY_FIELDS:
        val = getattr(intent, key, None)
        if not val:
            missing.append(label)
    return missing


def _is_blank(intent: TeachingIntent) -> bool:
    """是否没有任何实质内容。

    不能只写 `if not intent` —— dataclass 实例永远是真值，空对象也会被
    当成有效意图，给四路喂进去一段全是"（未确定）"的噪声。
    """
    if intent is None:
        return True
    return not any((
        intent.topic, intent.subject, intent.grade, intent.stage,
        intent.goals, intent.knowledgePoints, intent.focusPoints,
        intent.hardPoints, intent.methods, intent.interactions,
        intent.artifactKinds, intent.stylePreference,
        intent.learnerNote, intent.constraints,
    ))


def intent_to_prompt_text(intent: TeachingIntent) -> str:
    """把教学意图序列化成一段结构化文本，供四路生成共用。

    **四路必须用同一段文本** —— 否则教案、PPT、动画、游戏会对同一节课
    产生不同的理解。缺的字段就写"待教师补充"，不编造；整份为空则返回空串，
    不往 prompt 里塞噪声。
    """
    if _is_blank(intent):
        return ""

    def _lines(title: str, items: Iterable[str], empty_hint: str) -> List[str]:
        vals = [v for v in items if v]
        if not vals:
            return [f"- {title}：{empty_hint}"]
        return [f"- {title}：" + "；".join(vals)]

    out: List[str] = ["【教学意图】"]
    out.append(f"- 教学主题：{intent.topic or '（未确定）'}")
    out.append(f"- 学科：{intent.subject or '（未确定）'}")
    out.append(f"- 年级：{intent.grade or '（未确定）'}"
               + (f"（{intent.stage}）" if intent.stage else ""))
    out.append(f"- 课时：{intent.duration} 分钟")
    out += _lines("教学目标", intent.goals, "待教师补充")
    out += _lines("知识点", intent.knowledgePoints, "待教师补充")
    out += _lines("教学重点", intent.focusPoints, "待教师补充")
    out += _lines("教学难点", intent.hardPoints, "待教师补充")
    out += _lines("教学方法", intent.methods, "由教师常规做法决定")
    out += _lines("互动形式", intent.interactions, "由教学环节需要决定")
    if intent.artifactKinds:
        out.append(f"- 期望产物：{'、'.join(intent.artifactKinds)}")
    if intent.stylePreference:
        out.append(f"- 风格偏好：{intent.stylePreference}")
    if intent.learnerNote:
        out.append(f"- 学习者特征：{intent.learnerNote}")
    if intent.constraints:
        out.append(f"- 明确限制：{intent.constraints}")
    out.append("【教学意图完】")
    return "\n".join(out)
