"""教学蓝图（TeachingBlueprint）—— 生成前先给教师看的教学环节设计。

⚠️ 蓝图 ≠ 大纲（outline）
-------------------------
`/lesson-plan/generate-outline` 里的 outline 是**教案的章节结构**
（生成过程中的中间产物，喂给 generate-detailed-content 用）；
本模块的蓝图是**课堂环节设计**（导入 / 探究 / 讲解 / 练习 / 小结各做什么、
花多少分钟、产出什么）。两者不是一个东西，**不能复用 outline 字段**。

为什么不直接生成成品
--------------------
直接生成会出现"生成完才发现跑题"，教师只能整份重来。蓝图是一次低成本的
对齐：先让教师看到环节安排，确认或修改后再生成四类产物。

但**蓝图不能成为拦路虎**：
  * 蓝图生成失败 → 用离线模板兜底，并在 `error` 里写清原因；
  * 教师点"直接生成" → 跳过蓝图（`status='skipped'`）；
  两种情况都**不得阻断正式生成**。

存储约束
--------
只存结构化环节、摘要与引用关系，**绝不写教案/PPT 正文** —— 否则会破坏
既有任务台账"只存指针不存正文"的约定。所有字段长度封顶。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

__all__ = [
    "BlueprintStep", "TeachingBlueprint",
    "normalize_blueprint", "validate_blueprint",
    "blueprint_to_prompt_text", "template_blueprint",
]

MAX_STEPS = 12
_MAX_TEXT = 400
_MAX_ITEMS = 8


def _clean(v: Any, limit: int = _MAX_TEXT) -> str:
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
    if v is None:
        return []
    items = re.split(r"[；;\n]+", v) if isinstance(v, str) else list(v) \
        if isinstance(v, (list, tuple, set)) else []
    out: List[str] = []
    for it in items:
        s = _clean(it, 200)
        if s and s not in out:
            out.append(s)
        if len(out) >= _MAX_ITEMS:
            break
    return out


def _safe_int(v: Any, default: int = 0) -> int:
    """宽容解析里的 int() 不能真抛异常：时间字段来自模型与前端，
    "约 5 分钟"、None、嵌套结构都出现过。"""
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


def _minutes(v: Any) -> int:
    try:
        n = int(float(v))
    except (TypeError, ValueError):
        return 0
    return max(0, min(180, n))


@dataclass
class BlueprintStep:
    """一个教学环节。所有字段都有默认值，缺字段不会炸。"""
    id: str = ""
    name: str = ""
    purpose: str = ""
    teacherActivity: str = ""
    studentActivity: str = ""
    minutes: int = 0
    materials: List[str] = field(default_factory=list)
    interaction: str = ""
    output: str = ""
    knowledgeRefs: List[str] = field(default_factory=list)
    isKeyPoint: bool = False
    isHardPoint: bool = False
    risk: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "purpose": self.purpose,
            "teacherActivity": self.teacherActivity,
            "studentActivity": self.studentActivity,
            "minutes": self.minutes, "materials": list(self.materials),
            "interaction": self.interaction, "output": self.output,
            "knowledgeRefs": list(self.knowledgeRefs),
            "isKeyPoint": self.isKeyPoint, "isHardPoint": self.isHardPoint,
            "risk": self.risk,
        }


@dataclass
class TeachingBlueprint:
    id: str = ""
    lessonId: str = ""
    stages: List[BlueprintStep] = field(default_factory=list)
    totalMinutes: int = 0
    summary: str = ""
    status: str = "draft"          # draft | confirmed | skipped
    source: str = "template"       # model | template | teacher
    warnings: List[str] = field(default_factory=list)
    error: str = ""                # 生成失败原因（不阻断）
    createdAt: int = 0
    updatedAt: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "lessonId": self.lessonId,
            "stages": [s.to_dict() for s in self.stages],
            "totalMinutes": self.totalMinutes, "summary": self.summary,
            "status": self.status, "source": self.source,
            "warnings": list(self.warnings), "error": self.error,
            "createdAt": self.createdAt, "updatedAt": self.updatedAt,
        }


def normalize_blueprint(payload: Any = None) -> TeachingBlueprint:
    """宽容解析：任何形状都返回合法蓝图。老数据缺字段 → 空蓝图，不报错。"""
    if not isinstance(payload, dict):
        return TeachingBlueprint()

    stages: List[BlueprintStep] = []
    raw = payload.get("stages")
    if isinstance(raw, list):
        for i, item in enumerate(raw[:MAX_STEPS]):
            if not isinstance(item, dict):
                continue
            stages.append(BlueprintStep(
                id=_clean(item.get("id"), 40) or f"step-{i + 1}",
                name=_clean(item.get("name"), 60),
                purpose=_clean(item.get("purpose")),
                teacherActivity=_clean(item.get("teacherActivity")),
                studentActivity=_clean(item.get("studentActivity")),
                minutes=_minutes(item.get("minutes")),
                materials=_clean_list(item.get("materials")),
                interaction=_clean(item.get("interaction"), 200),
                output=_clean(item.get("output"), 200),
                knowledgeRefs=_clean_list(item.get("knowledgeRefs")),
                isKeyPoint=bool(item.get("isKeyPoint")),
                isHardPoint=bool(item.get("isHardPoint")),
                risk=_clean(item.get("risk"), 200),
            ))

    status = _clean(payload.get("status"), 20)
    if status not in ("draft", "confirmed", "skipped"):
        status = "draft"
    source = _clean(payload.get("source"), 20)
    if source not in ("model", "template", "teacher"):
        source = "template"

    total = _minutes(payload.get("totalMinutes"))
    if not total:
        total = sum(s.minutes for s in stages)

    return TeachingBlueprint(
        id=_clean(payload.get("id"), 40),
        lessonId=_clean(payload.get("lessonId"), 60),
        stages=stages,
        totalMinutes=total,
        summary=_clean(payload.get("summary"), 600),
        status=status,
        source=source,
        warnings=_clean_list(payload.get("warnings")),
        error=_clean(payload.get("error"), 400),
        createdAt=_safe_int(payload.get("createdAt"), 0),
        updatedAt=_safe_int(payload.get("updatedAt"), 0),
    )


def validate_blueprint(
    blueprint: TeachingBlueprint,
    intent: Any = None,
) -> List[str]:
    """质量提示，**只报告、不阻断**。

    返回的是给教师看的提示语，不是错误 —— 蓝图有瑕疵照样能生成。
    """
    warnings: List[str] = []

    if not blueprint.stages:
        warnings.append("蓝图还没有任何环节，建议先补充再生成")
        return warnings

    # 1) 时长与课时是否对得上
    want = getattr(intent, "duration", 0) or 0
    total = blueprint.totalMinutes or sum(s.minutes for s in blueprint.stages)
    if want and total and abs(total - want) > max(3, want * 0.1):
        warnings.append(
            f"各环节共 {total} 分钟，与设定课时 {want} 分钟不一致，建议调整")

    # 2) 环节是否缺必要类别
    names = "".join(s.name for s in blueprint.stages)
    activities = "".join(
        (s.interaction or "") + (s.teacherActivity or "") + (s.studentActivity or "")
        for s in blueprint.stages)
    if not any(k in names + activities for k in ("练习", "检测", "巩固", "训练")):
        warnings.append("没有看到课堂练习或检测环节，建议补一个")
    if not any(k in names + activities for k in ("小结", "总结", "归纳", "提升")):
        warnings.append("没有看到总结提升环节，建议补一个")
    if not any(k in names + activities for k in ("导入", "情境", "引入", "创设")):
        warnings.append("没有看到导入或情境创设环节，学生可能难以进入状态")

    # 3) 是否覆盖了声明的知识点与难点
    joined = "".join(
        (s.name or "") + (s.purpose or "") + "".join(s.knowledgeRefs)
        for s in blueprint.stages)
    for kp in getattr(intent, "knowledgePoints", None) or []:
        if kp and kp not in joined:
            warnings.append(f"知识点「{kp}」尚未出现在任何环节中")
    for hp in getattr(intent, "hardPoints", None) or []:
        if hp and hp not in joined and not any(
            s.isHardPoint for s in blueprint.stages):
            warnings.append(f"教学难点「{hp}」没有安排突破环节")

    # 4) 是否有环节没写时间
    no_time = [s.name or f"第{i + 1}环节"
               for i, s in enumerate(blueprint.stages) if not s.minutes]
    if no_time:
        warnings.append("这些环节没有填时间：" + "、".join(no_time))

    return warnings


def blueprint_to_prompt_text(blueprint: TeachingBlueprint) -> str:
    """把蓝图序列化成结构化文本，供**四路生成共用**。

    主题、知识点、重点难点、活动、时间安排都必须出现在这一段里 ——
    否则四路产物会各说各的（这正是"四路不一致"的根因）。

    ⚠️ **只有 `status='confirmed'` 的蓝图才注入**。
    `draft` 是模型刚生成、教师还没表态；`skipped` 是教师点了"直接生成"。
    把这两者也拼进 prompt，等于让一份**教师并没有认可**的安排去指导生成，
    而响应里还写着"已确认的环节安排，务必按此生成" —— 双重误导。
    """
    if not blueprint or not blueprint.stages:
        return ""
    if getattr(blueprint, "status", "draft") != "confirmed":
        return ""

    out: List[str] = ["【教学蓝图（教师已确认的环节安排，务必按此生成）】"]
    if blueprint.summary:
        out.append(f"整体思路：{blueprint.summary}")
    for i, s in enumerate(blueprint.stages, 1):
        head = f"{i}. {s.name or '未命名环节'}"
        if s.minutes:
            head += f"（{s.minutes} 分钟）"
        tags = []
        if s.isKeyPoint:
            tags.append("重点")
        if s.isHardPoint:
            tags.append("难点")
        if tags:
            head += "【" + "/".join(tags) + "】"
        out.append(head)
        if s.purpose:
            out.append(f"   目的：{s.purpose}")
        if s.teacherActivity:
            out.append(f"   教师活动：{s.teacherActivity}")
        if s.studentActivity:
            out.append(f"   学生活动：{s.studentActivity}")
        if s.interaction:
            out.append(f"   互动方式：{s.interaction}")
        if s.materials:
            out.append(f"   所需材料：{'、'.join(s.materials)}")
        if s.knowledgeRefs:
            out.append(f"   对应知识点：{'、'.join(s.knowledgeRefs)}")
        if s.output:
            out.append(f"   预期产出：{s.output}")
        if s.risk:
            out.append(f"   风险提示：{s.risk}")
    total = blueprint.totalMinutes or sum(s.minutes for s in blueprint.stages)
    if total:
        out.append(f"环节总时长：{total} 分钟")
    out.append("【教学蓝图完】")
    return "\n".join(out)


# ---- 模型生成 -------------------------------------------------------------
# 教师提出需求后**默认**走这里。但它是"锦上添花"而非必经关卡：
# 模型失败、返回格式不对、超时 —— 一律回落到 template_blueprint()，
# 并把原因写进 `error`，由上层提示教师"可以直接生成"。
_PROMPT = """你是资深教研员，请为一节课设计**教学蓝图**（课堂环节安排，不是教案全文）。

{intent_block}
{knowledge_block}
【总课时】{duration} 分钟

输出要求（严格 JSON，不要任何解释文字、不要 markdown 代码块）：
{{
  "summary": "一句话说明这节课的整体思路",
  "stages": [
    {{
      "name": "环节名称，如 情境导入",
      "purpose": "这个环节要解决什么",
      "teacherActivity": "教师做什么",
      "studentActivity": "学生做什么",
      "minutes": 5,
      "materials": ["所需材料"],
      "interaction": "互动方式，如 小组讨论",
      "output": "这个环节结束时学生产出什么",
      "knowledgeRefs": ["对应的知识点"],
      "isKeyPoint": false,
      "isHardPoint": false,
      "risk": "可能出现的风险与应对"
    }}
  ]
}}

约束：
1. 环节总时长必须等于总课时，误差不超过 2 分钟。
2. 必须包含：导入（或情境创设）、新知探究、巩固练习、总结提升。
3. 必须覆盖上面列出的**全部知识点**；教学难点要有专门的突破环节并标 isHardPoint。
4. 材料只写课堂真实可用的；不要设计做不到的活动。
5. 只输出 JSON。
"""


def _extract_json(raw: str) -> Optional[Dict[str, Any]]:
    """从模型输出里抠出 JSON。模型经常在 JSON 外面裹一堆话。"""
    import json

    text = (raw or "").strip()
    if not text:
        return None
    # 先去掉 ```json ... ``` 代码块
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    for candidate in (text,):
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except (ValueError, TypeError):
            pass
    # 退一步：截取第一个 { 到最后一个 }
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start:end + 1])
            if isinstance(data, dict):
                return data
        except (ValueError, TypeError):
            pass
    return None


def generate_blueprint(
    intent: Any = None,
    *,
    knowledge_text: str = "",
    provider: Optional[str] = None,
    lesson_id: str = "",
    topic: str = "",
    duration: int = 45,
) -> TeachingBlueprint:
    """调用模型生成教学蓝图；**任何失败都不抛出**，回落到离线模板。

    为什么失败也必须返回可用对象：蓝图是生成前的对齐环节，
    它挂了就让整个备课流程卡住，等于把"锦上添花"变成了"必经关卡"。
    教师赶时间时尤其不能这样。

    模型调用走 `llm_service`（出校插桩在它里面），这里**绝不直连 provider**。
    """
    from ..services.teaching_intent import (
        TeachingIntent, intent_to_prompt_text, normalize_teaching_intent,
    )

    it = intent if isinstance(intent, TeachingIntent) else normalize_teaching_intent(intent)
    if (not it.topic) and topic:
        it.topic = _clean(topic, 200)
    if not it.duration or it.duration == 45:
        if duration and duration != 45:
            it.duration = duration
    if duration and not it.duration:
        it.duration = duration

    dur = max(15, min(180, _safe_int(it.duration or duration or 45, 45)) or 45)
    fallback = template_blueprint(it.topic or topic, dur, intent=it, lesson_id=lesson_id)

    intent_block = intent_to_prompt_text(it) or "（教学意图尚未填写，请先按主题自行设计）"
    knowledge_block = ""
    if (knowledge_text or "").strip():
        knowledge_block = "【可参考的知识】\n" + knowledge_text.strip()[:2000]

    prompt = _PROMPT.format(
        intent_block=intent_block,
        knowledge_block=knowledge_block,
        duration=dur,
    )

    try:
        from .llm_service import llm_service
        raw = llm_service.chat(prompt, provider=provider) or ""
    except Exception as e:  # noqa: BLE001 —— 见上方说明：失败不得阻断
        fallback.error = f"蓝图生成调用失败：{type(e).__name__}"
        return fallback

    data = _extract_json(raw)
    if not data:
        fallback.error = "模型没有返回结构化的蓝图，已用通用骨架代替"
        return fallback

    data.setdefault("stages", [])
    bp = normalize_blueprint({
        "lessonId": lesson_id,
        "summary": data.get("summary"),
        "stages": data.get("stages"),
        "source": "model",
        "status": "draft",
    })
    if not bp.stages:
        fallback.error = "模型返回的蓝图没有可用环节，已用通用骨架代替"
        return fallback

    # 时长兜底：模型经常把时间加错。差太多就按比例重分配，而不是直接改一个环节
    total = sum(s.minutes for s in bp.stages)
    if dur and total and abs(total - dur) > 2:
        bp = _rescale_minutes(bp, dur)

    bp.warnings = validate_blueprint(bp, it)
    return bp


def _rescale_minutes(bp: TeachingBlueprint, target: int) -> TeachingBlueprint:
    """按环节原比例把总时长缩放到目标课时。

    不逐个环节硬改：那会打乱"导入短、探究长"的结构。按比例缩放再补齐余数，
    并把误差补到最长的那个环节上。
    """
    total = sum(s.minutes for s in bp.stages) or len(bp.stages)
    assigned = 0
    for i, s in enumerate(bp.stages):
        if i == len(bp.stages) - 1:
            s.minutes = max(1, target - assigned)
        else:
            s.minutes = max(1, round(target * (s.minutes or 1) / total))
            assigned += s.minutes
    bp.totalMinutes = sum(s.minutes for s in bp.stages)
    return bp


def template_blueprint(
    topic: str = "",
    duration: int = 45,
    *,
    intent: Any = None,
    lesson_id: str = "",
) -> TeachingBlueprint:
    """离线骨架蓝图：模型不可用时的兜底。

    **蓝图失败不能阻断生成** —— 用它兜住，并把原因写进 `error` 由上层展示。
    骨架按"导入—探究—讲解—练习—小结"五环节，时长按课时比例分配。
    """
    total = max(15, min(180, _safe_int(duration or 45, 45)) or 45)
    # 比例：导入 10%、探究 30%、讲解 25%、练习 25%、小结 10%
    weights = (0.10, 0.30, 0.25, 0.25, 0.10)
    names = ("情境导入", "探究活动", "新知讲解", "巩固练习", "总结提升")
    purposes = (
        "制造认知冲突，引出本课要解决的问题",
        "让学生先动手或讨论，收集证据与初步结论",
        "在学生经验之上抽象出概念或规律，给出规范表达",
        "分层练习，检验是否真正掌握并纠正共性错误",
        "回到目标自查，形成可迁移的结构",
    )
    topic_txt = (topic or getattr(intent, "topic", "") or "本课内容").strip()

    stages: List[BlueprintStep] = []
    assigned = 0
    for i, (name, purpose, w) in enumerate(zip(names, purposes, weights)):
        minutes = round(total * w)
        if i == len(weights) - 1:
            minutes = max(1, total - assigned)
        else:
            minutes = max(1, minutes)
            assigned += minutes
        stages.append(BlueprintStep(
            id=f"step-{i + 1}",
            name=name,
            purpose=purpose,
            teacherActivity="",
            studentActivity="",
            minutes=minutes,
            interaction="小组讨论" if name == "探究活动" else "",
            output="",
            knowledgeRefs=[],
            isKeyPoint=name in ("新知讲解", "探究活动"),
            isHardPoint=False,
            risk="",
        ))

    return TeachingBlueprint(
        id="",
        lessonId=lesson_id,
        stages=stages,
        totalMinutes=sum(s.minutes for s in stages),
        summary=f"围绕「{topic_txt}」的五环节骨架，供教师确认或修改",
        status="draft",
        source="template",
        warnings=["这是离线模板骨架，未结合本课知识点细化，建议确认后再生成"],
    )
