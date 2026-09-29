"""课程知识上下文：教案 / PPT / 动画 / 游戏四路生成共用同一份检索结果。

为什么要有这一层
----------------
四路生成此前**完全不查知识库**：模型只能凭自己的参数记忆备课。
于是同一节课，教案里的难点、PPT 里的表述、动画与游戏里的知识点各不相同 ——
教师看起来是"同一个系统给出了四套说法"。

现在四路都调本模块的 `build_course_context()`，同一节课拿到同一批片段，
四份产物的口径才可能对得上。

设计取舍
--------
* **检索失败绝不阻断生成**（红线精神的延伸）：任何异常都吞掉，返回空上下文。
  生成不该因为检索抖动而失败，最多是"这次没用到知识库"。
* **两路查询**：一路学科知识（概念与学生误区，供难点预判与内容准确性），
  一路教学策略（活动、实验、评价，供环节设计）。合并去重后统一截断。
* **过滤用得上就用**：subject 命中已知学科时按学科过滤；
  查不到就退回不过滤 —— 宁可拿到宽一点的结果，也不要空手而归。
"""
from __future__ import annotations

import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

log = logging.getLogger("course_knowledge")

# 与知识库 frontmatter 的 subject 取值保持一致
KNOWN_SUBJECTS = (
    "语文", "数学", "英语", "物理", "化学", "生物",
    "道德与法治", "历史", "地理", "科学", "信息科技", "艺术", "体育与健康",
)

# 动画 / 游戏接口传的是英文 key，这里统一成中文学科名
_SUBJECT_ALIASES = {
    "mathematics": "数学", "math": "数学",
    "physics": "物理",
    "chemistry": "化学",
    "biology": "生物",
    "geography": "地理",
    "chinese": "语文",
    "english": "英语",
    "general": "", "": "", "综合": "",
}

_KIND_HINT = {
    "lesson_plan": "教案",
    "ppt": "课件",
    "animation": "演示动画",
    "game": "课堂游戏",
}


# 知识库范围。与 retriever 的 origin 元数据对应（seed = 系统预置 / upload = 用户上传）。
# 之所以能直接复用 origin：上一轮已把来源标记统一成这一个字段，
# 所以"只用系统库"就是过滤 origin=seed，不需要新增任何索引结构。
KNOWLEDGE_SCOPES = ("system", "personal", "both", "none")

_SCOPE_NAMES = {
    "system": "系统教学知识库",
    "personal": "我的个人知识库",
    "both": "系统知识库 + 个人知识库",
    "none": "不使用知识库",
}


def scope_filters(scope: Optional[str]) -> Optional[Dict[str, Any]]:
    """知识库范围 → 检索过滤条件。未知值按 both（不过滤）处理，不静默变窄。"""
    if scope == "system":
        return {"origin": "seed"}
    if scope == "personal":
        return {"origin": "upload"}
    return None


@dataclass
class CourseKnowledge:
    """一次检索的结果。空结果也返回对象，方便调用方统一处理。"""
    text: str = ""                              # 可直接拼进 prompt 的文本块
    citations: List[Dict[str, str]] = field(default_factory=list)
    queries: List[str] = field(default_factory=list)
    empty: bool = True
    # 本次检索到底用上没有 —— 没用上必须说清原因，绝不伪造引用
    scope: str = "both"
    used: bool = False
    reason: str = ""
    # 本学科库内无命中、放宽到全库后才有结果 —— 含金量下降，必须让教师知道
    relaxed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "empty": self.empty,
            "queries": self.queries,
            "citations": self.citations,
            "chars": len(self.text),
            "scope": self.scope,
            "used": self.used,
            "reason": self.reason,
            "relaxed": self.relaxed,
        }


def normalize_subject(subject: Optional[str]) -> str:
    """把英文 key / 别名 / 空值统一成知识库里的中文学科名；认不出返回空串。"""
    raw = (subject or "").strip()
    if not raw:
        return ""
    if raw in KNOWN_SUBJECTS:
        return raw
    mapped = _SUBJECT_ALIASES.get(raw.lower(), "")
    if mapped in KNOWN_SUBJECTS:
        return mapped
    # 部分匹配：例如"初中物理"里含"物理"
    for name in KNOWN_SUBJECTS:
        if name and name in raw:
            return name
    return ""


def build_course_context(
    *,
    topic: str,
    subject: Optional[str] = None,
    grade: Optional[str] = None,
    audience: Optional[str] = None,
    key_points: Optional[Sequence[str]] = None,
    kind: Optional[str] = None,
    top_k: int = 4,
    method_top_k: int = 2,
    max_chars: int = 2400,
    enable_rerank: bool = True,
    scope: Optional[str] = "both",
    retriever=None,
    lesson_id: Optional[str] = None,
    use_snapshot: bool = True,
) -> CourseKnowledge:
    """检索这一节课该用的知识，返回可直接拼进 prompt 的文本块。

    `retriever` 可注入（测试用）；不传则用全局检索器。
    `scope` 见 KNOWLEDGE_SCOPES；缺省 both = **现有行为**，老调用方零感知。

    **同一节课共用同一批资料**：给了 `lesson_id`（或主题+学科+年级）且
    `use_snapshot=True` 时，命中缓存就原样返回上一次的检索结果 ——
    四路产物才会引用同一批依据，而不是各自检索一遍各引各的。
    缓存键**不含产物类型**，这正是为了保证四路命中同一份。

    **检索失败绝不阻断生成**：异常与拒答都吞掉，返回空上下文，
    并把原因写进 `reason` —— 上层必须原样展示给教师，不能伪造引用。
    """
    scope = scope if scope in KNOWLEDGE_SCOPES else "both"
    result = CourseKnowledge(scope=scope)
    topic = (topic or "").strip()

    snap_key = ""
    if use_snapshot:
        snap_key = _snapshot_key(
            lesson_id=str(lesson_id or ""), topic=topic,
            subject=subject or "",
            who=(grade or "").strip() or (audience or "").strip(),
            scope=scope)
        cached = get_snapshot(snap_key)
        if cached is not None:
            return cached
        if not topic and not (lesson_id or "").strip():
            snap_key = ""

    if not topic:
        result.reason = "未指定教学主题，本次未检索"
        return result

    if scope == "none":
        result.reason = "教师选择本次不使用知识库"
        return result

    subj = normalize_subject(subject)
    who = (grade or "").strip() or (audience or "").strip()
    hint = _KIND_HINT.get(kind or "", "教学")

    q1 = " ".join(x for x in (topic, subj, who, "核心概念 学生常见错误 教学难点") if x)
    q2 = f"{topic} {hint} 教学设计 课堂活动 实验 评价"
    result.queries = [q1, q2]

    if retriever is None:
        try:
            from ..rag.retriever import get_retriever
            retriever = get_retriever()
        except Exception as e:  # noqa: BLE001
            log.warning("课程知识检索不可用，本次生成不带知识库: %s", e)
            result.reason = f"知识库不可用：{type(e).__name__}"
            return result

    # 范围过滤与学科过滤是**并列条件**：{"subject": "物理", "origin": "seed"} 表示
    # 既要物理、又要属于系统库。未知 scope 已在开头归一为 both（不过滤）。
    base_scope = scope_filters(scope)
    refused_flags: List[bool] = []
    hits: List[Dict[str, Any]] = []
    seen: set = set()
    relaxed = False

    def _collect(query: str, k: int, filters: Optional[Dict[str, Any]],
                 reject_other_subject: str = "") -> None:
        try:
            res = retriever.retrieve(query, top_k=k, filters=filters,
                                     enable_rerank=enable_rerank)
        except Exception as e:  # noqa: BLE001
            log.warning("课程知识检索失败(%s): %s", query[:24], e)
            return
        if getattr(res, "refused", False):
            refused_flags.append(True)
            return
        for h in getattr(res, "hits", []) or []:
            if reject_other_subject:
                # 放宽学科后：明确属于**别的**学科的片段不能当本科依据
                hit_subj = normalize_subject(
                    (getattr(h, "metadata", None) or {}).get("subject"))
                if hit_subj and hit_subj != reject_other_subject:
                    continue
            cid = getattr(h, "chunk_id", None) or h.raw_text[:64]
            if cid in seen:
                continue
            seen.add(cid)
            hits.append({
                "text": h.text,
                "raw_text": h.raw_text,
                "source": h.source,
                "heading_path": h.heading_path,
                "score": h.score,
            })

    def _merge(base: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not base_scope:
            return base
        return {**(base or {}), **base_scope}

    # 1) 学科知识：按学科过滤
    filters1 = {"subject": subj} if subj else None
    _collect(q1, top_k, _merge(filters1))
    if not hits and filters1:
        # 本学科库里确实没有 → 放宽学科再找一次。**但绝不能把别的学科内容
        # 当成本科依据**：放宽后仍按 metadata.subject 剔除明确属于其他学科的片段，
        # 并在文本里写明"已放宽"，让教师知道含金量下降了。
        before = len(hits)
        _collect(q1, top_k, _merge(None), reject_other_subject=subj)
        if len(hits) > before:
            relaxed = True

    # 2) 教学策略
    _collect(q2, method_top_k,
             _merge({"type": "教学法"} if kind in ("lesson_plan", "ppt") else None))

    if not hits:
        # 必须说清"为什么没用上" —— 检索失败、拒答、还是本就没有。
        # 上层要原样展示给教师，绝不能伪造引用假装查到了。
        result.reason = (
            "本次未能检索到相关知识（知识库判定为无关），生成内容请教师核验"
            if refused_flags else "本次未能检索到相关知识，生成内容请教师核验")
        return result

    lines: List[str] = []
    total = 0
    for h in hits:
        piece = (h.get("raw_text") or "").strip()
        if not piece:
            continue
        cite = h.get("source") or ""
        path = h.get("heading_path") or ""
        if total + len(piece) > max_chars:
            break
        lines.append(f"- {piece}\n  （依据：{cite}｜{path}）" if (cite or path) else f"- {piece}")
        total += len(piece)
        result.citations.append({"source": cite, "heading_path": path})

    if not lines:
        return result

    header = f"【课程知识参考（范围：{_SCOPE_NAMES.get(scope, scope)}；"
    header += "与本次生成内容一致性相关，请优先采纳）】"
    if relaxed:
        header += "\n（提示：本学科库内没有直接命中，以下为放宽学科后的内容，请教师核验）"
    result.text = header + "\n" + "\n".join(lines) + "\n【参考完】"
    result.empty = False
    result.used = True
    result.relaxed = relaxed
    result.reason = ""
    # 只有真正用上了才进缓存：检索抖动导致的空不该让后续三路一起空着
    if snap_key:
        _remember_snapshot(snap_key, result)
    return result


# ---------------------------------------------------------------------------
# 知识快照：同一节课的四路产物必须引用**同一批**资料
# ---------------------------------------------------------------------------
# 光有"同一个组装函数"不够：四路仍在各自时机、各自参数下各检索一遍，
# 检索有随机性（rerank 批次不同、query 里带了各自的产物类型词），
# 于是教案引用 A/B、PPT 引用 C/D —— 四份产物口径对不上。
# 这里按 (课程 id / 主题+学科+年级, 范围) 缓存一次检索结果，四路共用同一份。
_SNAPSHOT_TTL = 1800          # 秒：够覆盖"一键生成全部"的整个过程
_SNAPSHOT_MAX = 32            # 最多缓存多少节课，防止无限增长
_SNAPSHOTS: "OrderedDict[str, tuple]" = OrderedDict()


def _snapshot_key(*, lesson_id: str, topic: str, subject: str,
                  who: str, scope: str) -> str:
    # 有课程 id 就用它（最稳）；没有就退化成"主题+学科+年级" ——
    # 注意**不包含产物类型**：四路要命中同一个 key，才可能共用同一批资料。
    base = (lesson_id or "").strip()
    if not base:
        base = "|".join(((topic or "").strip(), (subject or "").strip(),
                         (who or "").strip()))
    return f"{base}::{scope}"


def _remember_snapshot(key: str, knowledge: CourseKnowledge) -> None:
    _SNAPSHOTS[key] = (time.time(), knowledge)
    # 过期与超量一起清：只在写入时清理，不引入后台线程
    now = time.time()
    for k in [k for k, (t, _) in _SNAPSHOTS.items() if now - t > _SNAPSHOT_TTL]:
        _SNAPSHOTS.pop(k, None)
    while len(_SNAPSHOTS) > _SNAPSHOT_MAX:
        _SNAPSHOTS.popitem(last=False)


def get_snapshot(key: str) -> Optional[CourseKnowledge]:
    hit = _SNAPSHOTS.get(key)
    if not hit:
        return None
    ts, knowledge = hit
    if time.time() - ts > _SNAPSHOT_TTL:
        _SNAPSHOTS.pop(key, None)
        return None
    return knowledge


def clear_snapshots() -> None:
    """仅供测试与"重新检索"场景：清空快照缓存。"""
    _SNAPSHOTS.clear()


def compose_generation_context(
    *,
    topic: str,
    subject: Optional[str] = None,
    grade: Optional[str] = None,
    audience: Optional[str] = None,
    key_points: Optional[Sequence[str]] = None,
    kind: Optional[str] = None,
    scope: Optional[str] = "both",
    blueprint: Any = None,
    intent: Any = None,
    lesson_id: Optional[str] = None,
    use_snapshot: bool = True,
    top_k: int = 4,
    method_top_k: int = 2,
    max_chars: int = 2400,
    enable_rerank: bool = True,
) -> Tuple[CourseKnowledge, str, Dict[str, Any]]:
    """四路生成**唯一**的上下文组装入口。

    为什么必须收成一个函数：教案 / PPT / 动画 / 游戏此前各拼各的，
    于是同一节课拿到四段不同的上下文 —— 四份产物口径不一致的根因就在这里。

    组装顺序（越具体越靠后，模型越容易记住）：
      ① 检索到的知识（可溯源） → ② 教学意图 → ③ 教学蓝图（最贴近课堂执行）

    **任何一步失败都不阻断**：知识没检索到就只带意图与蓝图；意图为空就跳过；
    蓝图缺失（教师点了"直接生成"）也照样生成。

    返回 `(knowledge, text, meta)`。`meta` 说清三件事各用上了没有 ——
    上层要把它原样回给教师，尤其是"蓝图其实没用上"不能报成用上了。
    """
    from .teaching_blueprint import blueprint_to_prompt_text, normalize_blueprint
    from .teaching_intent import (
        TeachingIntent, intent_to_prompt_text, normalize_teaching_intent,
    )

    knowledge = build_course_context(
        topic=topic, subject=subject, grade=grade, audience=audience,
        key_points=key_points, kind=kind, scope=scope,
        top_k=top_k, method_top_k=method_top_k, max_chars=max_chars,
        enable_rerank=enable_rerank,
        lesson_id=lesson_id, use_snapshot=use_snapshot,
    )

    parts: List[str] = []
    if knowledge.text:
        parts.append(knowledge.text)

    meta: Dict[str, Any] = {
        "knowledge_used": bool(knowledge.used),
        "intent_used": False,
        "blueprint_used": False,
        "blueprint_status": "",
        "shared_snapshot": bool(use_snapshot),
    }

    if intent is not None:
        it = intent if isinstance(intent, TeachingIntent) \
            else normalize_teaching_intent(intent)
        it_text = intent_to_prompt_text(it)
        if it_text:
            parts.append(it_text)
            meta["intent_used"] = True

    if blueprint is not None:
        bp = blueprint if hasattr(blueprint, "stages") else normalize_blueprint(blueprint)
        meta["blueprint_status"] = getattr(bp, "status", "") or ""
        bp_text = blueprint_to_prompt_text(bp)
        if bp_text:
            parts.append(bp_text)
            meta["blueprint_used"] = True

    return knowledge, "\n\n".join(parts), meta


def append_to_requirements(requirements: str, knowledge: CourseKnowledge) -> str:
    """把知识块拼进"补充需求"。四路共用的拼接方式，避免各处格式不一。"""
    if knowledge.empty or not knowledge.text:
        return requirements or ""
    base = (requirements or "").strip()
    return f"{base}\n\n{knowledge.text}".strip() if base else knowledge.text
