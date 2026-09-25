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
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

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


@dataclass
class CourseKnowledge:
    """一次检索的结果。空结果也返回对象，方便调用方统一处理。"""
    text: str = ""                              # 可直接拼进 prompt 的文本块
    citations: List[Dict[str, str]] = field(default_factory=list)
    queries: List[str] = field(default_factory=list)
    empty: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "empty": self.empty,
            "queries": self.queries,
            "citations": self.citations,
            "chars": len(self.text),
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
    retriever=None,
) -> CourseKnowledge:
    """检索这一节课该用的知识，返回可直接拼进 prompt 的文本块。

    `retriever` 可注入（测试用）；不传则用全局检索器。
    """
    result = CourseKnowledge()
    topic = (topic or "").strip()
    if not topic:
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
            return result

    hits: List[Dict[str, Any]] = []
    seen: set = set()

    def _collect(query: str, k: int, filters: Optional[Dict[str, Any]]) -> None:
        try:
            res = retriever.retrieve(query, top_k=k, filters=filters,
                                     enable_rerank=enable_rerank)
        except Exception as e:  # noqa: BLE001
            log.warning("课程知识检索失败(%s): %s", query[:24], e)
            return
        if getattr(res, "refused", False):
            return
        for h in getattr(res, "hits", []) or []:
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

    # 1) 学科知识：按学科过滤；过滤后查不到就退回不过滤（宁宽勿空）
    filters1 = {"subject": subj} if subj else None
    _collect(q1, top_k, filters1)
    if not hits and filters1:
        _collect(q1, top_k, None)

    # 2) 教学策略
    _collect(q2, method_top_k, {"type": "教学法"} if kind in ("lesson_plan", "ppt") else None)

    if not hits:
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

    result.text = (
        "【课程知识参考（来自内置知识库，与本次生成内容一致性相关，请优先采纳）】\n"
        + "\n".join(lines)
        + "\n【参考完】"
    )
    result.empty = False
    return result


def append_to_requirements(requirements: str, knowledge: CourseKnowledge) -> str:
    """把知识块拼进"补充需求"。四路共用的拼接方式，避免各处格式不一。"""
    if knowledge.empty or not knowledge.text:
        return requirements or ""
    base = (requirements or "").strip()
    return f"{base}\n\n{knowledge.text}".strip() if base else knowledge.text
