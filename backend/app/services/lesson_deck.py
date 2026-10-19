"""课件的结构化契约与校验器 —— 把"能上课"翻译成可验收的规则。

为什么要有这一层
----------------
此前生成链路的终点是"一堆文本 + 一个版式"，于是产出了「选择题：关于X的核心概念」
这种凑页数的页——因为它没有教学功能，也没有任何规则拦住它。

本模块做的事：
  1. 定义 12 种**教学功能页**（不是排版版式）的必填字段
  2. 校验：占位符 0 容忍、教学闭环齐全、每页内容非空
  3. 按标准文档的 5 维量规打分，**总分 <20 或任一维 <3 判定不合格**

页面类型来自标准文档的「标准页面骨架」，字段名对齐 12 份黄金样例。
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

GOLDEN_PATH = os.path.join("knowledge_base", "golden_decks", "decks.json")

# ---------------------------------------------------------------------------
# 1. 12 种教学功能页的字段契约
# ---------------------------------------------------------------------------
# 注意：cover 的课题/年级/版本在 deck 层（meta），不在 slide 里。

PAGE_SPEC: Dict[str, Dict[str, Any]] = {
    "cover": {"required": [], "cn": "封面"},
    "objectives": {"required": ["items"], "cn": "学习目标", "min_items": 2, "max_items": 4},
    "divider": {"required": ["title"], "cn": "板块分隔"},
    "points": {"required": ["title", "items"], "cn": "要点/情境导入", "min_items": 1},
    "concept": {"required": ["title", "big", "points"], "cn": "新知概念", "min_items": 1},
    "example": {"required": ["title", "problem", "steps", "answer"], "cn": "例题示范", "min_items": 1},
    "activity": {"required": ["title", "goal", "steps"], "cn": "活动/实验", "min_items": 1},
    "exercise": {"required": ["title", "items"], "cn": "巩固练习", "min_items": 1},
    "table": {"required": ["title", "headers", "rows"], "cn": "对比表格", "min_items": 1},
    "summary": {"required": ["title", "items"], "cn": "课堂小结", "min_items": 1},
    "homework": {"required": ["title", "required"], "cn": "作业布置", "min_items": 1},
    "end": {"required": [], "cn": "结束页"},
}

# 教学闭环：缺任何一段都不算"能承载一节课"
CLOSURE_STAGES = [
    ("导入", ("points", "divider")),
    ("新知", ("concept", "points", "example", "table")),
    ("活动", ("activity", "example")),
    ("练习", ("exercise",)),
    ("小结", ("summary",)),
    ("作业", ("homework",)),
]

# ---------------------------------------------------------------------------
# 2. 占位符硬门槛
# ---------------------------------------------------------------------------
# 标准原文：不得出现「请填写、待补充、TODO、此处插入、示例内容、老师自行设计、图片来源」
PLACEHOLDER_PATTERNS = [
    r"请填写", r"待补充", r"TODO", r"TBD", r"此处插入", r"示例内容",
    r"自行设计", r"图片来源", r"请自行", r"自行补充", r"略）", r"此处添加",
    r"XXX+", r"PXX", r"\{\}", r"教师：\s*X",
    r"待定", r"课堂上补充", r"根据实际情况补充",
    # 长串下划线才是"留白待填"（如 授课教师 ________）；
    # 短下划线是**合法的填空线**（英语题 My mother is in the ____.），不能误杀。
    r"＿{4,}", r"_{6,}",
]
_PH_RE = re.compile("|".join(PLACEHOLDER_PATTERNS), re.I)


def find_placeholders(text: str, *, in_question: bool = False) -> List[str]:
    """扫描占位符。

    @param in_question True 表示这段文字是**题目正文**——题目里的短下划线
                       是合法的填空线，只有"待补充/TODO"这类别算占位。
    """
    hits = _PH_RE.findall(text or "")
    if not in_question:
        return hits
    # 题目里放行纯下划线（去掉下划线类命中）
    return [h for h in hits if not re.fullmatch(r"[＿_]+", h)]


# ---------------------------------------------------------------------------
# 3. 教师备注（标准第 6 条要求每页有；黄金样例本身也没有，故列为建议项）
# ---------------------------------------------------------------------------
NOTE_FIELDS = ("say", "ask", "minutes", "transition")


def note_of(slide: Dict[str, Any]) -> Dict[str, str]:
    n = slide.get("teacher_note") or {}
    return {k: str(n.get(k) or "").strip() for k in NOTE_FIELDS}


# ---------------------------------------------------------------------------
# 4. 校验
# ---------------------------------------------------------------------------

def _nonempty(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, (list, tuple)):
        return any(_nonempty(x) for x in v)
    return True


def _all_text(deck: Dict[str, Any]) -> str:
    """把整份课件拼成文本，供占位符扫描。"""
    return json.dumps(deck, ensure_ascii=False)


def validate_deck(deck: Dict[str, Any]) -> Dict[str, Any]:
    """校验一份课件。

    @returns {ok, errors[], warnings[], scores{}, missing_stages[]}
             ok = 无 error 且 5 维总分 ≥20 且无维度 <3
    """
    errors: List[str] = []
    warnings: List[str] = []
    deck = deck or {}

    meta = deck.get("meta") or deck
    topic = str(meta.get("topic") or meta.get("title") or "").strip()
    if not topic:
        errors.append("缺少课题（meta.topic）")
    if not str(meta.get("subject") or "").strip():
        errors.append("缺少学科（meta.subject）")

    slides = deck.get("slides") or []
    if not isinstance(slides, list) or not slides:
        errors.append("没有页面（slides 为空）")
        return {"ok": False, "errors": errors, "warnings": warnings,
                "scores": {}, "missing_stages": [s[0] for s in CLOSURE_STAGES]}

    # 4.1 占位符（硬门槛，0 容忍）
    # 题目正文里的短下划线是合法填空线，单独扫描以免误杀
    ph: List[str] = []
    for s in slides:
        for key, val in s.items():
            if key == "items" and isinstance(val, list):
                # 列表逐项扫：题干(q) 放行填空线，其余字段一律严查
                for it in val:
                    if isinstance(it, dict):
                        for k2, v2 in it.items():
                            if k2 == "q":
                                ph += find_placeholders(str(v2 or ""), in_question=True)
                            else:
                                ph += find_placeholders(str(v2 or ""))
                    else:
                        ph += find_placeholders(str(it))
                continue
            if key in ("problem", "goal", "big", "title", "answer", "tip", "note"):
                # 题干/结论类：短下划线是合法填空线
                ph += find_placeholders(str(val or ""), in_question=(key == "problem"))
                continue
            ph += find_placeholders(json.dumps(val, ensure_ascii=False))
    ph += find_placeholders(json.dumps(
        {k: v for k, v in meta.items() if k != "slides"}, ensure_ascii=False))
    if ph:
        errors.append(f"存在占位符 {len(ph)} 处：{sorted(set(ph))[:5]}")

    # 4.2 页面数量（标准：一节课 15–25 页）
    if len(slides) < 10:
        warnings.append(f"页数偏少（{len(slides)} 页，建议 15–25 页）")

    # 4.3 逐页校验
    types = []
    for i, s in enumerate(slides):
        t = str(s.get("type") or "").strip()
        if t not in PAGE_SPEC:
            errors.append(f"第{i + 1}页 未知页面类型「{t}」")
            continue
        types.append(t)
        spec = PAGE_SPEC[t]
        for f in spec.get("required", []):
            if not _nonempty(s.get(f)):
                errors.append(f"第{i + 1}页({spec['cn']}) 缺少必填字段「{f}」")
        # 列表类字段不能是空列表
        for key in ("items", "steps", "rows", "required"):
            v = s.get(key)
            if v is not None and isinstance(v, list) and not v:
                errors.append(f"第{i + 1}页({spec['cn']}) 「{key}」为空列表")
        mni = spec.get("min_items")
        if mni and isinstance(s.get("items"), list) and len(s["items"]) < mni:
            errors.append(f"第{i + 1}页({spec['cn']}) items 少于 {mni} 条")

    # 4.4 练习必须有答案（学生要能自检）
    for i, s in enumerate(slides):
        if s.get("type") == "exercise":
            for j, it in enumerate(s.get("items") or []):
                if isinstance(it, dict) and not _nonempty(it.get("a")):
                    errors.append(f"第{i + 1}页 练习第{j + 1}题缺少答案（a）")

    # 4.5 教学闭环
    missing = [cn for cn, allowed in CLOSURE_STAGES
               if not any(t in allowed for t in types)]
    # 标准原文：六段齐全是**合格线**。缺一段就不是"能承载一节课"的课件，
    # 不能只扣分——扣分的话去掉练习页仍能拿到 20 分以上，等于放过去。
    if missing:
        errors.append(f"教学闭环缺失：{'、'.join(missing)}")

    # 4.6 教师备注（建议项：黄金样例也没有，但生成物应该有）
    no_note = [i + 1 for i, s in enumerate(slides)
               if not any(note_of(s).values())]
    if no_note:
        warnings.append(f"{len(no_note)} 页缺少教师备注（建议每页都有：讲什么/问什么/几分钟/过渡语）")

    scores = score_deck(deck, errors, missing, no_note, len(slides))
    total = sum(scores.values())
    ok = (not errors) and total >= 20 and all(v >= 3 for v in scores.values())
    return {"ok": ok, "errors": errors, "warnings": warnings,
            "scores": scores, "total": total, "missing_stages": missing,
            "page_count": len(slides)}


def score_deck(deck: Dict[str, Any], errors: List[str], missing: List[str],
               no_note: List[int], pages: int) -> Dict[str, int]:
    """标准文档的 5 维量规，每维 0–5 分。"""
    slides = deck.get("slides") or []

    # 1 内容成品度：占位符 + 必填缺失
    c1 = 5
    if any("占位符" in e for e in errors):
        c1 = 0
    c1 -= min(3, sum(1 for e in errors if "缺少必填" in e or "为空列表" in e))
    c1 = max(0, c1)

    # 2 教学流程闭环：缺一段扣 1
    c2 = max(0, 5 - len(missing))

    # 3 每页教学功能：有内容页占比
    functional = sum(1 for s in slides if s.get("type") in
                     ("concept", "example", "activity", "exercise", "table", "points"))
    c3 = 5 if functional >= 6 else (4 if functional >= 4 else (3 if functional >= 2 else 1))

    # 4 学科适配：有学科专属页（例题/实验/表格/活动）才算适配，而不是通用要点堆
    has_subject_page = any(s.get("type") in ("example", "activity", "table") for s in slides)
    c4 = 4 if has_subject_page else 2
    meta = deck.get("meta") or deck
    if str(meta.get("version") or "").strip():
        c4 = min(5, c4 + 1)

    # 5 密度/可读性：页数在合理区间、无超长段落
    c5 = 5 if 15 <= pages <= 25 else (4 if 12 <= pages <= 28 else 3)
    longest = 0
    for s in slides:
        for k in ("problem", "answer", "goal", "big"):
            longest = max(longest, len(str(s.get(k) or "")))
    if longest > 160:
        c5 = max(2, c5 - 1)

    return {"内容成品度": c1, "教学闭环": c2, "每页功能": c3,
            "学科适配": c4, "密度可读": c5}


# ---------------------------------------------------------------------------
# 5. 黄金样例
# ---------------------------------------------------------------------------

def load_golden() -> List[Dict[str, Any]]:
    try:
        if os.path.exists(GOLDEN_PATH):
            with open(GOLDEN_PATH, "r", encoding="utf-8") as f:
                return json.load(f).get("decks", [])
    except Exception:
        pass
    return []


def find_golden(subject: str, topic: str) -> Optional[Dict[str, Any]]:
    """按学科 + 课题找黄金样例，供 few-shot 或直接复用。"""
    best, best_score = None, 0
    for d in load_golden():
        s = str(d.get("subject") or "").strip()
        t = str(d.get("title") or d.get("topic") or "").strip()
        if subject and s != subject:
            continue
        sc = 100 if t == topic else (60 if topic and topic in t else 0)
        if sc > best_score:
            best, best_score = d, sc
    return best


def golden_fewshot(subject: str, limit: int = 2) -> str:
    """给 LLM 的 few-shot 示例文本（同学科的黄金样例优先）。"""
    decks = [d for d in load_golden()
             if not subject or str(d.get("subject") or "").strip() == subject]
    if not decks:
        decks = load_golden()
    out = []
    for d in decks[:limit]:
        sample = {
            "meta": {k: d.get(k) for k in ("band", "grade", "subject", "version", "topic", "period")
                     if d.get(k)},
            "slides": d.get("slides", [])[:6],
        }
        out.append(json.dumps(sample, ensure_ascii=False, indent=1))
    return "\n\n".join(out)
