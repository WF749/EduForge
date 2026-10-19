"""教材索引查询：这个知识点在本册教材的哪一章哪一节第几页。

设计定位
--------
**只做定位，不存正文。** 教材 PDF 版权归出版社，把正文塞进仓库是我们自己的
侵权风险；索引里只有目录结构（章/节标题 + 页码），用它回答"教到哪了"。

最重要的行为是**答不上来要老实说 None**：
本地没有那本教材时（实测：浮力在物理八年级**下册**，而本地只有上册），
必须返回 None，让生成链路降级到知识点大纲。
编造"八年级下册第10章"这种章节号，比不提供更有害 —— 那是幻觉。

索引来源：`scripts/build_textbook_index.py` 从本地教材 PDF 自动提取。
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

INDEX_PATH = os.path.join("knowledge_base", "textbooks", "index.json")

_cache: Optional[Dict[str, Any]] = None
_cache_loaded = False


# 学段/年级归一：用户输入"初二"，教材写"八年级"
_GRADE_ALIAS = {
    "初一": "七年级", "初二": "八年级", "初三": "九年级",
    "高一": "高一", "高二": "高二", "高三": "高三",
}


def _norm_grade(g: str) -> str:
    return _GRADE_ALIAS.get((g or "").strip(), (g or "").strip())


def load(force: bool = False) -> Dict[str, Any]:
    """加载索引（进程内缓存一次）。缺文件或损坏时返回空索引而不是抛错。"""
    global _cache, _cache_loaded
    if _cache_loaded and not force:
        return _cache or {"books": []}
    _cache_loaded = True
    try:
        if os.path.exists(INDEX_PATH):
            with open(INDEX_PATH, "r", encoding="utf-8") as f:
                _cache = json.load(f)
        else:
            _cache = {"books": []}
    except Exception:
        _cache = {"books": []}
    return _cache


def _books_for(subject: str, grade: str) -> List[Dict[str, Any]]:
    subj = (subject or "").strip()
    grd = _norm_grade(grade)
    out = []
    for b in load().get("books", []):
        if subj and b.get("subject") != subj:
            continue
        if grd and b.get("grade") and b.get("grade") != grd:
            continue
        out.append(b)
    return out


def _score(title: str, topic: str) -> int:
    """标题与课题的匹配度：命中越长越可信。"""
    t = (title or "").strip()
    q = (topic or "").strip()
    if not t or not q:
        return 0
    if t == q:
        return 100
    if q in t:
        return 60 + len(q) * 2
    if t in q:
        return 40 + len(t) * 2
    # 逐字命中（"浮力" vs "阿基米德原理" 不会误命中，因为共享字少）
    common = len(set(t) & set(q))
    return common * 3 if common >= 2 else 0


def lookup(subject: str, grade: str, topic: str) -> Optional[Dict[str, Any]]:
    """定位课题在教材中的位置。

    @returns None 表示"本地没有可依据的教材" —— 调用方必须据此降级，
             绝不能自己编一个章节号。
    """
    q = (topic or "").strip()
    if not q or not subject:
        return None

    best: Optional[Dict[str, Any]] = None
    for book in _books_for(subject, grade):
        for unit in book.get("units", []):
            us = _score(unit.get("title", ""), q)
            if us and (best is None or us > best["score"]):
                best = {"score": us, "book": book, "chapter": unit,
                        "section": None}
            for sec in unit.get("sections", []):
                ss = _score(sec.get("title", ""), q)
                if ss and (best is None or ss > best["score"]):
                    best = {"score": ss, "book": book, "chapter": unit,
                            "section": sec}

    if not best or best["score"] < 20:
        return None

    book, chap = best["book"], best["chapter"]
    sec = best["section"]
    return {
        "found": True,
        "subject": book.get("subject"),
        "grade": book.get("grade"),
        "band": book.get("band"),
        "version": book.get("version") or "",
        "volume": book.get("volume") or "",
        "chapter": f"第{chap.get('no')}章 {chap.get('title', '')}".strip(),
        "section": (f"第{sec['no']}节 {sec.get('title', '')}".strip() if sec else ""),
        "page": (sec or chap).get("page"),
        "source": "本地教材目录索引",
        # 明确告诉调用方这是从目录定位来的，不是教材正文
        "note": "来自教材目录索引（仅用于定位，不含正文）",
    }


def describe(subject: str, grade: str, topic: str) -> str:
    """给 prompt 用的一句话描述；查不到就明确说"本地暂无对应教材"。"""
    hit = lookup(subject, grade, topic)
    if not hit:
        return (f"本地教材库中没有「{subject}{grade or ''}」与「{topic}」对应的教材目录，"
                f"请按学科知识点体系自行组织内容，不要编造教材章节号。")
    parts = [hit["version"], hit["grade"] or "", hit["volume"], hit["subject"]]
    head = " ".join(p for p in parts if p)
    loc = hit["chapter"] + (f" {hit['section']}" if hit["section"] else "")
    return f"参考教材：{head}。本课题位于 {loc}（教材第 {hit['page']} 页）。"


def available_books() -> List[Dict[str, str]]:
    """列出本地已建索引的教材，供设置页展示。"""
    return [{"subject": b.get("subject"), "grade": b.get("grade"),
             "volume": b.get("volume"), "version": b.get("version"),
             "units": len(b.get("units", []))}
            for b in load().get("books", [])]
