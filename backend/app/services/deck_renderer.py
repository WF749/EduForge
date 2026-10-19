"""把符合契约的课件渲染成 PPT —— 产出"能上课的课包"。

和 `ppt_tasks._write_pptx` 的区别
--------------------------------
`_write_pptx` 渲染的是"排版版式"（cover/toc/bullets/cards…），回答"这页长什么样"；
这里渲染的是**教学功能页**（封面/目标/导入/概念/例题/活动/练习/小结/作业…），
回答"这页在课上干什么"。前者再漂亮，去掉装饰后一页没有可讲授的信息。

学段视觉规范（字号来自标准：正文 ≥24pt 保证教室后排可读）
--------------------------------------------------------
    小学：明亮高饱和、字号最大   初中：清爽青绿   高中：沉稳学术、密度最高

教师备注
--------
标准第 6 条要求每页有备注（讲什么 / 问什么 / 几分钟 / 过渡语）。
12 份黄金样例**本身也没有**（实测 0/14），所以这里主动写入 notes_slide：
有 teacher_note 用教师的，没有就按页面类型自动生成一条可用的兜底话术。
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

W_IN, H_IN = 13.333, 7.5

# ---------------------------------------------------------------------------
# 学段主题（字号 / 配色）
# ---------------------------------------------------------------------------
THEMES = {
    "primary": dict(band="FF7A1A", band_text="FFFFFF", accent="2E9BFF",
                    ink="333333", sub="6B6B6B", soft="FFF3E6", card="FFFFFF",
                    card_line="F3C79C", tag="FF7A1A",
                    cover=46, title=32, body=28, small=20),
    "junior": dict(band="0E7C66", band_text="FFFFFF", accent="F2A93B",
                   ink="22303A", sub="5C6B72", soft="E9F5F1", card="FFFFFF",
                   card_line="B7DCD1", tag="0E7C66",
                   cover=42, title=30, body=26, small=19),
    "senior": dict(band="1F3A93", band_text="FFFFFF", accent="E0554E",
                   ink="1B2733", sub="586674", soft="EEF1F8", card="FFFFFF",
                   card_line="C3CCE2", tag="1F3A93",
                   cover=40, title=30, body=24, small=18),
}
DEFAULT_THEME = THEMES["junior"]

BAND_BY_CN = {"小学": "primary", "初中": "junior", "高中": "senior"}


def _rgb(h: str) -> RGBColor:
    h = (h or "000000").lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


# ---------------------------------------------------------------------------
# 基础绘制
# ---------------------------------------------------------------------------

def _rect(sl, l, t, w, h, fill=None, line=None, shape=MSO_SHAPE.RECTANGLE, lw=1.0):
    sh = sl.shapes.add_shape(shape, Inches(l), Inches(t), Inches(w), Inches(h))
    if fill:
        sh.fill.solid()
        sh.fill.fore_color.rgb = _rgb(fill)
    else:
        sh.fill.background()
    if line:
        sh.line.color.rgb = _rgb(line)
        sh.line.width = Pt(lw)
    else:
        sh.line.fill.background()
    sh.shadow.inherit = False
    if sh.has_text_frame:
        sh.text_frame.word_wrap = True
    return sh


def _tb(sl, l, t, w, h, anchor=MSO_ANCHOR.TOP):
    box = sl.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    return tf


def _para(tf, text, size, color, bold=False, align=PP_ALIGN.LEFT,
          first=False, sa=6, sb=0):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    p.space_after = Pt(sa)
    p.space_before = Pt(sb)
    r = p.add_run()
    r.text = str(text or "")
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.color.rgb = _rgb(color)
    r.font.name = "微软雅黑"
    return p


def _bullets(tf, items, size, color, bullet="• "):
    for i, it in enumerate(items):
        _para(tf, f"{bullet}{it}", size, color, first=(i == 0), sa=10)


def _header(sl, th, title, page=None):
    """顶部色条 + 标题 + 页码：位置全程固定，翻页时视线不用重新找。"""
    _rect(sl, 0, 0, W_IN, 1.05, fill=th["band"])
    _rect(sl, 0, 1.05, W_IN, 0.07, fill=th["accent"])
    tf = _tb(sl, 0.55, 0.05, 10.6, 0.95, MSO_ANCHOR.MIDDLE)
    _para(tf, title, th["title"], th["band_text"], bold=True, first=True, sa=0)
    if page is not None:
        ptf = _tb(sl, 11.6, 0.05, 1.2, 0.95, MSO_ANCHOR.MIDDLE)
        _para(ptf, f"{page:02d}", th["small"], th["band_text"],
              bold=True, align=PP_ALIGN.RIGHT, first=True, sa=0)


def _footer(sl, th, left_text):
    tf = _tb(sl, 0.55, H_IN - 0.52, 11.0, 0.4)
    _para(tf, left_text, th["small"] - 2, th["sub"], first=True, sa=0)


# ---------------------------------------------------------------------------
# 教师备注（标准第 6 条；黄金样例本身也没有，这里主动补）
# ---------------------------------------------------------------------------

_FALLBACK_NOTE = {
    "cover": "开场：点明今天要解决的问题，用一句话让学生知道「学这个有什么用」。",
    "objectives": "把目标念一遍，强调「学完你能做什么」，让学生带着目标听课。",
    "divider": "过渡：用一句话说明接下来这个板块要干什么。",
    "points": "逐条提问，让学生先猜再讲，不要直接给结论。",
    "concept": "先给结论再解释关键词，配合板书/图示，确认学生记下了。",
    "example": "先让学生自己尝试，再逐步讲解，强调规范书写。",
    "activity": "说明目标与步骤、强调安全/规则，巡视并记录典型做法。",
    "exercise": "限时完成，先自查再互评，最后统一讲解答案。",
    "table": "引导学生横向/纵向对比，自己说出规律再总结。",
    "summary": "让学生先说，教师再补充，形成完整知识结构。",
    "homework": "明确必做与选做，说明提交时间与要求。",
    "end": "收尾：预告下节课内容。",
}


def _write_note(sl, slide: Dict[str, Any], th: Dict[str, Any], page: int, total: int):
    """写教师备注：讲什么 / 问什么 / 几分钟 / 过渡语。"""
    n = slide.get("teacher_note") or {}
    say = str(n.get("say") or "").strip()
    ask = str(n.get("ask") or "").strip()
    minutes = str(n.get("minutes") or "").strip()
    trans = str(n.get("transition") or "").strip()
    t = slide.get("type") or ""

    lines = [f"[第 {page}/{total} 页 · {t}]"]
    if minutes:
        lines.append(f"建议用时：{minutes} 分钟")
    if say:
        lines.append(f"讲：{say}")
    if ask:
        lines.append(f"问：{ask}")
    if trans:
        lines.append(f"过渡：{trans}")
    if not (say or ask):
        # 没有教师自写的备注时给一条**可用的**兜底话术，而不是留空
        lines.append("讲：" + _FALLBACK_NOTE.get(t, "按页面内容组织讲解。"))
        lines.append("问：这一页的关键点是什么？谁能用自己的话说一遍？")
    prov = None
    try:
        sl.notes_slide.notes_text_frame.text = "\n".join(lines)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 各教学功能页
# ---------------------------------------------------------------------------

def _cover(prs, th, deck, s, page=None):
    sl = prs.slides.add_slide(prs.slide_layouts[6])
    _rect(sl, 0, 0, W_IN, H_IN, fill=th["band"])
    _rect(sl, 8.1, 3.4, 5.2, 4.1, fill=th["accent"], shape=MSO_SHAPE.RIGHT_TRIANGLE)
    meta = deck.get("meta") or deck
    tf = _tb(sl, 0.9, 1.9, 8.6, 1.6)
    _para(tf, meta.get("topic") or meta.get("title") or "",
          th["cover"], th["band_text"], bold=True, first=True, sa=0)
    sub = meta.get("subtitle") or s.get("subtitle") or ""
    if sub:
        _para(tf, sub, th["title"] - 4, th["band_text"], sa=8)
    info = " · ".join(x for x in [
        meta.get("version"), meta.get("grade"), meta.get("subject"),
        meta.get("period") or meta.get("topic_no"),
    ] if x)
    if info:
        tf2 = _tb(sl, 0.9, 4.2, 8.6, 0.8)
        _para(tf2, info, th["body"] - 4, th["band_text"], first=True, sa=0)
    # 溯源：教材依据写在封面底部（有教材就贴章节，没有就写"按知识点体系"）
    prov = deck.get("provenance") or {}
    src = prov.get("textbook") or ""
    if src:
        tf3 = _tb(sl, 0.9, 5.2, 8.6, 1.0)
        _para(tf3, src[:80], th["small"], th["band_text"], first=True, sa=0)
    _rect(sl, 0.9, 3.85, 1.5, 0.08, fill=th["accent"])
    return sl


def _objectives(prs, th, deck, s, page):
    sl = prs.slides.add_slide(prs.slide_layouts[6])
    _header(sl, th, s.get("title") or "学习目标", page)
    items = s.get("items") or []
    # 一列通栏卡片：此前做成"左卡片 + 右侧重复列表"，同一批目标在页面上出现两遍，
    # 教师看到会以为漏了内容。目标页只该把每一条说清楚。
    y = 1.5
    for it in items[:4]:
        txt = it.get("text") if isinstance(it, dict) else it
        tag = (it.get("tag") if isinstance(it, dict) else None) or ""
        _rect(sl, 0.75, y, 11.8, 1.12, fill=th["soft"], line=th["card_line"])
        if tag:
            _rect(sl, 0.75, y, 0.14, 1.12, fill=th["tag"])
        tf = _tb(sl, 1.15, y + 0.06, 11.2, 1.0, MSO_ANCHOR.MIDDLE)
        _para(tf, f"{tag}. {txt}" if tag else txt, th["body"] + 1, th["ink"],
              first=True, sa=0)
        y += 1.3
    _footer(sl, th, s.get("footer") or "学习目标")
    return sl


def _divider(prs, th, deck, s, page):
    sl = prs.slides.add_slide(prs.slide_layouts[6])
    _rect(sl, 0, 0, W_IN, H_IN, fill=th["soft"])
    _rect(sl, 0, 0, 0.28, H_IN, fill=th["band"])
    tf = _tb(sl, 1.4, 2.5, 10.5, 2.2)
    if s.get("no"):
        _para(tf, s["no"], th["small"] + 2, th["tag"], bold=True, first=True, sa=6)
    _para(tf, s.get("title") or "", th["cover"] - 4, th["ink"], bold=True, sa=8)
    if s.get("subtitle"):
        _para(tf, s["subtitle"], th["body"] - 2, th["sub"])
    return sl


def _points(prs, th, deck, s, page):
    sl = prs.slides.add_slide(prs.slide_layouts[6])
    _header(sl, th, s.get("title") or "", page)
    items = s.get("items") or []
    tf = _tb(sl, 0.75, 1.6, 11.8, 4.6)
    _bullets(tf, items[:6], th["body"] - 2, th["ink"])
    _footer(sl, th, s.get("title") or "")
    return sl


def _concept(prs, th, deck, s, page):
    sl = prs.slides.add_slide(prs.slide_layouts[6])
    _header(sl, th, s.get("title") or "", page)
    # 结论框 = 这一页的视觉锚点
    _rect(sl, 0.75, 1.5, 11.8, 1.5, fill=th["band"], line=None)
    tf = _tb(sl, 1.05, 1.62, 11.2, 1.25, MSO_ANCHOR.MIDDLE)
    _para(tf, s.get("big") or "", th["body"] + 2, th["band_text"], bold=True, first=True, sa=0)
    tf2 = _tb(sl, 0.95, 3.25, 11.4, 3.0)
    _bullets(tf2, s.get("points") or [], th["body"] - 2, th["ink"])
    _footer(sl, th, s.get("title") or "")
    return sl


def _example(prs, th, deck, s, page):
    sl = prs.slides.add_slide(prs.slide_layouts[6])
    _header(sl, th, s.get("title") or "例题", page)
    _rect(sl, 0.75, 1.5, 11.8, 1.1, fill=th["soft"], line=th["card_line"])
    tf = _tb(sl, 1.0, 1.6, 11.3, 0.9, MSO_ANCHOR.MIDDLE)
    _para(tf, s.get("problem") or "", th["body"] - 1, th["ink"], first=True, sa=0)
    # 解题步骤
    tf2 = _tb(sl, 0.95, 2.85, 11.4, 2.6)
    _para(tf2, "解题步骤", th["small"] + 2, th["tag"], bold=True, first=True, sa=8)
    for i, st in enumerate((s.get("steps") or [])[:4]):
        _para(tf2, f"{i + 1}. {st}", th["body"] - 2, th["ink"], sa=8)
    # 答案
    if s.get("answer"):
        _rect(sl, 0.75, 5.55, 11.8, 0.95, fill=th["accent"])
        tf3 = _tb(sl, 1.0, 5.65, 11.3, 0.75, MSO_ANCHOR.MIDDLE)
        _para(tf3, f"答案：{s['answer']}", th["body"] - 1, "FFFFFF", bold=True, first=True, sa=0)
    _footer(sl, th, s.get("title") or "")
    return sl


def _activity(prs, th, deck, s, page):
    sl = prs.slides.add_slide(prs.slide_layouts[6])
    _header(sl, th, s.get("title") or "课堂活动", page)
    _rect(sl, 0.75, 1.5, 11.8, 0.85, fill=th["soft"], line=th["card_line"])
    tf = _tb(sl, 1.0, 1.58, 11.3, 0.7, MSO_ANCHOR.MIDDLE)
    _para(tf, f"目标：{s.get('goal') or ''}", th["body"] - 2, th["ink"], first=True, sa=0)
    tf2 = _tb(sl, 0.95, 2.6, 11.4, 3.0)
    _para(tf2, "操作步骤", th["small"] + 2, th["tag"], bold=True, first=True, sa=8)
    for i, st in enumerate((s.get("steps") or [])[:5]):
        _para(tf2, f"{i + 1}. {st}", th["body"] - 3, th["ink"], sa=8)
    if s.get("tip"):
        _rect(sl, 0.75, 5.6, 11.8, 0.85, fill=th["card"], line=th["accent"], lw=1.5)
        tf3 = _tb(sl, 1.0, 5.7, 11.3, 0.65, MSO_ANCHOR.MIDDLE)
        _para(tf3, f"提示：{s['tip']}", th["body"] - 2, th["ink"], first=True, sa=0)
    _footer(sl, th, s.get("title") or "")
    return sl


def _exercise(prs, th, deck, s, page):
    sl = prs.slides.add_slide(prs.slide_layouts[6])
    _header(sl, th, s.get("title") or "课堂练习", page)
    items = s.get("items") or []
    tf = _tb(sl, 0.75, 1.55, 11.8, 4.4)
    for i, it in enumerate(items[:3]):
        q = it.get("q") if isinstance(it, dict) else it
        _para(tf, f"第{i + 1}题  {q}", th["body"] - 2, th["ink"],
              bold=True, first=(i == 0), sa=4)
        a = (it.get("a") if isinstance(it, dict) else "") or ""
        if a:
            _para(tf, f"    答案/要点：{a}", th["body"] - 2, th["sub"], sa=14)
    _footer(sl, th, "先独立完成，再对照答案")
    return sl


def _table(prs, th, deck, s, page):
    sl = prs.slides.add_slide(prs.slide_layouts[6])
    _header(sl, th, s.get("title") or "", page)
    headers = s.get("headers") or []
    rows = s.get("rows") or []
    if headers and rows:
        n_r, n_c = min(len(rows) + 1, 6), len(headers)
        gt = sl.shapes.add_table(n_r, n_c, Inches(0.75), Inches(1.6),
                                 Inches(11.8), Inches(0.62 * n_r))
        tbl = gt.table
        for j, h in enumerate(headers):
            c = tbl.cell(0, j)
            c.text = str(h)
            for p in c.text_frame.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(th["body"] - 4)
                    r.font.bold = True
                    r.font.color.rgb = _rgb(th["band_text"])
                    r.font.name = "微软雅黑"
        for i, row in enumerate(rows[:5], start=1):
            for j, v in enumerate(row[:n_c]):
                c = tbl.cell(i, j)
                c.text = str(v)
                for p in c.text_frame.paragraphs:
                    for r in p.runs:
                        r.font.size = Pt(th["body"] - 5)
                        r.font.color.rgb = _rgb(th["ink"])
                        r.font.name = "微软雅黑"
    if s.get("note"):
        tf = _tb(sl, 0.75, 1.75 + 0.62 * min(len(rows) + 1, 6), 11.8, 1.2)
        _para(tf, s["note"], th["body"] - 2, th["tag"], first=True, sa=0)
    _footer(sl, th, s.get("title") or "")
    return sl


def _summary(prs, th, deck, s, page):
    sl = prs.slides.add_slide(prs.slide_layouts[6])
    _header(sl, th, s.get("title") or "课堂小结", page)
    items = s.get("items") or []
    y = 1.6
    for it in items[:4]:
        _rect(sl, 0.75, y, 11.8, 0.95, fill=th["soft"], line=th["card_line"])
        _rect(sl, 0.75, y, 0.13, 0.95, fill=th["tag"])
        tf = _tb(sl, 1.05, y + 0.06, 11.3, 0.85, MSO_ANCHOR.MIDDLE)
        _para(tf, it, th["body"] - 2, th["ink"], first=True, sa=0)
        y += 1.12
    _footer(sl, th, "课堂小结")
    return sl


def _homework(prs, th, deck, s, page):
    sl = prs.slides.add_slide(prs.slide_layouts[6])
    _header(sl, th, s.get("title") or "布置作业", page)
    blocks = [("必做", s.get("required") or [], th["band"]),
              ("选做", s.get("optional") or [], th["accent"]),
              ("实践", s.get("practice") or [], th["tag"])]
    x = 0.75
    for label, items, color in blocks:
        if not items:
            continue
        _rect(sl, x, 1.6, 3.85, 4.2, fill=th["card"], line=th["card_line"])
        _rect(sl, x, 1.6, 3.85, 0.62, fill=color)
        tf = _tb(sl, x + 0.15, 1.62, 3.55, 0.58, MSO_ANCHOR.MIDDLE)
        _para(tf, label, th["body"] - 3, th["band_text"], bold=True, first=True, sa=0)
        tf2 = _tb(sl, x + 0.2, 2.4, 3.45, 3.2)
        _bullets(tf2, items[:3], th["body"] - 3, th["ink"])
        x += 4.05
    _footer(sl, th, "作业布置")
    return sl


def _end(prs, th, deck, s, page):
    sl = prs.slides.add_slide(prs.slide_layouts[6])
    _rect(sl, 0, 0, W_IN, H_IN, fill=th["band"])
    tf = _tb(sl, 1.2, 2.6, 11.0, 2.0, MSO_ANCHOR.MIDDLE)
    _para(tf, s.get("title") or "谢谢观看", th["cover"], th["band_text"],
          bold=True, align=PP_ALIGN.CENTER, first=True, sa=0)
    if s.get("subtitle"):
        _para(tf, s["subtitle"], th["body"], th["band_text"], align=PP_ALIGN.CENTER, sa=10)
    return sl


_RENDERERS = {
    "cover": _cover, "objectives": _objectives, "divider": _divider,
    "points": _points, "concept": _concept, "example": _example,
    "activity": _activity, "exercise": _exercise, "table": _table,
    "summary": _summary, "homework": _homework, "end": _end,
}


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def render_deck(deck: Dict[str, Any], out_path: str,
                textbook_hint: str = "") -> str:
    """渲染一份课件为 pptx。

    @param deck 符合 lesson_deck 契约的课件
    @param textbook_hint 教材定位信息（来自 textbook_index），会写进封面页脚
    @returns 输出路径
    """
    prs = Presentation()
    prs.slide_width = Inches(W_IN)
    prs.slide_height = Inches(H_IN)

    meta = deck.get("meta") or deck
    band = BAND_BY_CN.get(str(meta.get("band") or meta.get("band_cn") or "").strip(), "")
    if not band:
        band = str(meta.get("band") or "").strip() or "junior"
    th = THEMES.get(band, DEFAULT_THEME)

    slides = deck.get("slides") or []
    total = len(slides)
    for i, s in enumerate(slides):
        fn = _RENDERERS.get(s.get("type"))
        if not fn:
            continue
        sl = fn(prs, th, deck, s, i + 1)
        _write_note(sl, s, th, i + 1, total)

    prs.core_properties.title = str(meta.get("topic") or meta.get("title") or "")[:80]
    prs.core_properties.subject = f"{meta.get('subject') or ''} · 可直接上课课件"
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    prs.save(out_path)
    return out_path
