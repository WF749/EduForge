"""Background PPT generation tasks (polled by /ppt/status)."""
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import llm_client
from .paths import GENERATED_CW
from .services.text_render import safe_text

_lock = threading.Lock()
TASKS: Dict[str, Dict[str, Any]] = {}


def _update(tid: str, **kwargs: Any) -> None:
    with _lock:
        if tid in TASKS:
            TASKS[tid].update(kwargs)


def _theme_rgb(theme_name: str) -> Tuple[int, int, int]:
    n = theme_name or ""
    if "绿" in n:
        return (0, 128, 96)
    if "红" in n or "粉" in n:
        return (192, 48, 72)
    if "紫" in n:
        return (112, 48, 160)
    if "橙" in n or "金" in n:
        return (220, 120, 40)
    return (0, 112, 192)


def _build_detailed_content(topic: str, outline: str, audience: str) -> List[Dict[str, Any]]:
    """Convert outline to slide definitions. 支持多行outline（含缩进子项）。"""

    # 学科关键词映射
    subject_keywords = {
        "数学": ["定义", "公式", "定理", "例题", "证明", "应用"],
        "物理": ["原理", "定律", "公式", "实验", "现象", "应用"],
        "化学": ["元素", "反应", "方程式", "实验", "性质", "应用"],
        "生物": ["结构", "功能", "过程", "实验", "进化", "生态"],
        "编程": ["概念", "语法", "算法", "案例", "调试", "实践"],
        "计算机": ["原理", "架构", "算法", "实现", "优化", "应用"],
        "英语": ["词汇", "语法", "阅读", "写作", "口语", "翻译"],
        "语文": ["文学", "写作", "阅读", "修辞", "文化", "鉴赏"],
        "历史": ["时间线", "事件", "人物", "背景", "影响", "评价"],
        "地理": ["地形", "气候", "资源", "人口", "城市", "环境"],
    }

    # 检测学科
    detected_subject = "综合"
    for subject, keywords in subject_keywords.items():
        if any(keyword in topic for keyword in keywords) or subject in topic:
            detected_subject = subject
            break

    slides = [
        {
            "page_num": 1,
            "page_type": "cover",
            "core_topic": topic,
            "main_title": topic,
            "subtitle": f"面向 {audience} ｜ {detected_subject}课程 ｜ 互动式教学课件",
        },
        {
            "page_num": 2,
            "page_type": "toc",
            "core_topic": "本课结构",
            "main_title": "课程目录",
            "bullet_points": "学习目标 · 核心概念 · 原理讲解 · 例题练习 · 课堂互动 · 总结延伸",
        },
    ]

    # 解析大纲行：第一级是非缩进行（页面标题），第二级是缩进行（内容要点）
    raw_lines = outline.splitlines()
    outline_pages = []  # [(title, [bullet1, bullet2, ...]), ...]
    current_title = None
    current_bullets = []

    for line in raw_lines:
        stripped = line.strip()
        if not stripped or len(stripped) < 2:
            continue

        # 判断是否为缩进行（以 - * • · 或两个以上空格开头）
        is_indented = (
            line.startswith("  ") or line.startswith("\t")
            or stripped.startswith("-") or stripped.startswith("*")
            or stripped.startswith("•") or stripped.startswith("·")
        )

        # 清理前缀符号
        clean = stripped.lstrip("-*•·0123456789.）) \t")

        if is_indented:
            # 缩进行 = 当前页面的要点
            if current_title and clean:
                current_bullets.append(clean)
            elif not current_title and clean:
                # 没有标题的情况下，缩进行提升为标题
                current_title = clean
                current_bullets = []
        else:
            # 非缩进行 = 新页面标题
            if current_title:
                outline_pages.append((current_title, current_bullets))
            current_title = clean
            current_bullets = []

    # 保存最后一页
    if current_title:
        outline_pages.append((current_title, current_bullets))

    # 如果大纲为空，生成默认内容
    if not outline_pages:
        outline_pages = [
            (f"{topic} - 基础概念", []),
            (f"{topic} - 核心原理", []),
            (f"{topic} - 实践应用", []),
            (f"{topic} - 典型案例", []),
            (f"{topic} - 课堂练习", []),
        ]

    n = 3
    for title, bullets in outline_pages[:12]:
        core_topic = title[:80]
        if bullets:
            bp = "\n".join(f"• {b}" for b in bullets[:8])
        else:
            bp = (
                f"• {core_topic}的定义与核心内涵\n"
                f"• {core_topic}的关键特征与要素\n"
                f"• {core_topic}的实际应用场景\n"
                f"• 学习{core_topic}的注意事项"
            )
        slides.append(
            {
                "page_num": n,
                "page_type": "content",
                "core_topic": core_topic,
                "main_title": core_topic,
                "bullet_points": bp,
            }
        )
        n += 1
        if n > 16:
            break

    # ---- 收尾两页 ------------------------------------------------------
    # 此前这里无条件追加两句硬编码废话（「选择题：关于X的核心概念」），
    # 于是无论前面的内容生成得多好，教师翻到倒数两页看到的永远是敷衍。
    # 现在：大纲里已经有练习/小结就不再重复加；要补也从**已有的概念**里提炼，
    # 保证是这节课真正讲过的东西。
    titles = [s.get("core_topic") or "" for s in slides if s.get("page_type") == "content"]
    joined = " ".join(titles)
    has_exercise = any(k in joined for k in ("练习", "检测", "检测题", "巩固", "当堂"))
    has_summary = any(k in joined for k in ("小结", "总结", "回顾", "收获"))

    if not has_exercise:
        picks = [t for t in titles if t][:3]
        if picks:
            body = "\n".join(
                f"• 回顾：请用一句话说明「{t}」的关键结论" for t in picks)
            body += "\n• 互评：同桌交换答案，指出彼此遗漏的条件"
        else:
            body = f"• 请用自己的话复述{topic}的核心思路"
        slides.append({
            "page_num": n, "page_type": "exercise",
            "core_topic": "当堂检测", "main_title": f"{topic} · 当堂检测",
            "bullet_points": body,
        })
        n += 1

    if not has_summary:
        lines = [f"• {t}" for t in titles[:5]]
        if not lines:
            lines = [f"• {topic}的核心要点"]
        lines.append("• 课后：完成配套练习，并记录一个仍存疑的问题")
        slides.append({
            "page_num": n, "page_type": "summary",
            "core_topic": "课堂小结", "main_title": "本课小结",
            "bullet_points": "\n".join(lines),
        })

    return slides


def _theme_palette(theme_name: str) -> Dict[str, Tuple[int, int, int]]:
    """整套主题色。

    为什么集中成一张色表而不是只给一个"主色"：课件要能一眼看出层次
    （封面压得住、正文读得清、强调跳得出），靠单色加不出层次。
    每张表给 5 个语义角色：主色 / 辅色 / 强调 / 深色底 / 浅色底。
    """
    n = theme_name or ""
    if "绿" in n:
        p, s, a = (0x0F, 0x6B, 0x5A), (0x2E, 0xA0, 0x84), (0xF2, 0xB1, 0x3C)
        dark, light = (0x0B, 0x3B, 0x32), (0xF2, 0xF7, 0xF5)
    elif "红" in n or "粉" in n:
        p, s, a = (0xA8, 0x28, 0x3C), (0xD6, 0x52, 0x5E), (0xF0, 0xC2, 0x33)
        dark, light = (0x5A, 0x12, 0x1E), (0xFB, 0xF5, 0xF5)
    elif "紫" in n:
        p, s, a = (0x5B, 0x3A, 0x9E), (0x87, 0x6B, 0xD6), (0xF0, 0xA8, 0x3C)
        dark, light = (0x2E, 0x1D, 0x52), (0xF7, 0xF4, 0xFC)
    elif "橙" in n or "金" in n:
        p, s, a = (0xC4, 0x6A, 0x1C), (0xE8, 0x93, 0x3E), (0x2E, 0x86, 0xAB)
        dark, light = (0x6B, 0x33, 0x08), (0xFD, 0xF8, 0xF2)
    else:  # 蓝色系（默认）
        p, s, a = (0x14, 0x5D, 0x9C), (0x2E, 0x8B, 0xD6), (0xF2, 0xA6, 0x2C)
        dark, light = (0x0B, 0x2C, 0x4C), (0xF4, 0xF8, 0xFC)
    return {
        "primary": p, "secondary": s, "accent": a,
        "dark": dark, "light": light,
        "text": (0x22, 0x2C, 0x38), "muted": (0x60, 0x6C, 0x7A),
        "white": (0xFF, 0xFF, 0xFF),
    }


# ---------------------------------------------------------------------------
# 画布与母版：统一按 1280×720 的像素网格设计，再换算成 EMU
# ---------------------------------------------------------------------------
# 为什么要固定母版三区：课堂 PPT 翻页时，标题和页码如果逐页乱跳，学生的视线
# 每页都要重新找焦点。A/B/C 三区 + 固定页码位，是"看起来专业"最便宜的一招。
_PX = 9525                      # 96dpi：1px = 9525 EMU
_CANVAS_W, _CANVAS_H = 1280, 720
_PAD_X = 72
_A_TOP, _A_H = 0, 120           # A · 标题块
_B_TOP, _B_H = 120, 540         # B · 内容区
_C_TOP, _C_H = 660, 60          # C · 页脚条


def _px(v: int) -> int:
    return int(v * _PX)


# 版式库。同一份内容可以用不同版式承载 —— 版式重复是"观感廉价"的主因。
_LAYOUTS = ("cover", "toc", "bullets", "cards", "compare", "formula", "emphasis", "summary")


def _fit_size(text: str, width_px: int, height_px: int,
              sizes: tuple = (26, 24, 22, 20, 18, 17, 16, 15, 14)) -> int:
    """按可用空间选字号，保证这段文字**放得下**。

    为什么必须算：python-pptx 不会自动收缩文字，字号给大了就直接溢出 ——
    实测出现过正文压到页脚线上、卡片内两段字叠在一起。自动排版拿不到渲染结果，
    只能按"中文 1 字符 ≈ 1 个字宽"保守估算行数。
    """
    n = max(len(text), 1)
    for s in sizes:
        # 字号的单位是 pt，可用空间是 px（1pt ≈ 1.33px），行距再按 1.6 算 ——
        # 少乘这个 1.33 就会低估行高，实测把 34pt 的文字排出了色块边界。
        per_line = max(1, int(width_px / (s * 1.34)))
        lines = (n + per_line - 1) // per_line
        if lines * s * 2.15 <= height_px:
            return s
    return sizes[-1]


def _clip(text: str, width_px: int, height_px: int, size: int) -> str:
    """在给定字号下放不下的部分截断并加省略号。

    宁可少显示几个字，也不能让文字压到别的元素上 —— 溢出比截断难看得多。
    """
    per_line = max(1, int(width_px / (size * 1.34)))
    max_lines = max(1, int(height_px / (size * 2.15)))
    limit = per_line * max_lines
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)].rstrip("，。；、 ") + "…"


def _pick_layout(i: int, prev: str, title: str, lines: List[str]) -> str:
    """按内容特征选版式，并避免与上一页重复。

    判据只用**内容自身**（有没有公式符号、有没有对比结构、要点几条），
    不猜用户意图 —— 那是教学需求的事，不属于排版层。
    """
    text = title + " " + " ".join(lines)
    has_formula = bool(re.search(r"[=＝]|_\{?\w+\}?|ρ|Ω|Δ|[₀-₉]|[⁰-⁹]|√|≤|≥|×|÷", text))
    compare = bool(re.search(r"(vs|VS|对比|区别|不同|而非|而不是|左|右)", title)) or (
        len(lines) >= 2 and any(re.search(r"(＞|＜|≥|≤|大于|小于)", l) for l in lines[:3]))

    # 公式页：只认"标题里就有等号"这一个强信号。
    # 此前把含 × / ρ / ≥ 之类符号的页也算进来，结果一份课件里 7 页连着都是
    # 公式版式 —— 反而比全部一种版式更单调。有等号才说明这页的主角是式子。
    eq_in_title = bool(re.search(r"[=＝]", title))
    if eq_in_title and len(lines) <= 6:
        want = "formula"
    elif compare and len(lines) == 2:
        # 只有正好两条时才二分；硬拆三句会让卡片一半是空白
        want = "compare"
    elif 2 <= len(lines) <= 3 and all(len(l) <= 34 for l in lines):
        want = "cards"
    elif len(lines) == 1 or (lines and len(lines[0]) <= 46):
        want = "emphasis"
    else:
        want = "bullets"
    # 连续两页同版式会让整份课件显得单调，一律参与去重
    return want if want != prev else ("bullets" if want != "bullets" else "cards")


def _write_pptx(path: Path, topic: str, detailed: List[Dict[str, Any]], theme_name: str,
                images: "Dict[int, str] | None" = None) -> None:
    """把幻灯片定义写成 PPTX。

    三条设计纪律（照专业课件排版的做法，而非"填占位符"）：

    1. **母版三区**：A 标题块 / B 内容区 / C 页脚条，标题与页码位置全程固定。
    2. **每页一个视觉锚点**：超大数字、大色块或大字号。所有元素都差不多大小
       的页面，看起来就是"一堆文字"。
    3. **版式不重复**：按内容特征在封面/目录/要点/卡片/对比/公式/强调/总结
       之间选，且与上一页不同。

    刻意不用母版占位符：占位符排出来每页都是"白底 + 标题 + 项目符号"。
    """
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Pt

    images = images or {}
    T = _theme_palette(theme_name)
    C = {k: RGBColor(*v) for k, v in T.items()}

    prs = Presentation()
    prs.slide_width = _px(_CANVAS_W)
    prs.slide_height = _px(_CANVAS_H)
    blank = prs.slide_layouts[6] if len(prs.slide_layouts) > 6 else prs.slide_layouts[0]
    total = min(len(detailed), 36)

    def _fill(shape, color):
        shape.fill.solid()
        shape.fill.fore_color.rgb = color
        shape.line.fill.background()

    def _box(sl, x, y, w, h, color=None, shape=MSO_SHAPE.RECTANGLE):
        sh = sl.shapes.add_shape(shape, _px(x), _px(y), _px(w), _px(h))
        if color is None:
            sh.fill.background()
            sh.line.fill.background()
        else:
            _fill(sh, color)
        sh.shadow.inherit = False
        return sh

    def _tb(sl, x, y, w, h):
        box = sl.shapes.add_textbox(_px(x), _px(y), _px(w), _px(h))
        box.text_frame.word_wrap = True
        return box.text_frame

    def _rich(tf, text, size, color, bold=False, first=False):
        """写入一段文字，并把 `X_浮` / `cm³` 这类写法排成上下标。"""
        para = tf.paragraphs[0] if first else tf.add_paragraph()
        para.alignment = PP_ALIGN.LEFT
        for base, sub, sup in _split_script(text):
            run = para.add_run()
            run.text = base
            run.font.size = Pt(size)
            run.font.bold = bold
            run.font.color.rgb = color
            run.font.name = "Microsoft YaHei"
            if sub or sup:
                r2 = para.add_run()
                r2.text = sub or sup
                r2.font.size = Pt(max(8, size - 4))
                r2.font.bold = bold
                r2.font.color.rgb = color
                r2.font.name = "Microsoft YaHei"
                try:
                    from pptx.oxml.ns import qn
                    r2.font._rPr.set("baseline", "-25000" if sub else "30000")
                except Exception:
                    pass
        return para

    def _footer(sl, idx):
        tf = _tb(sl, _CANVAS_W - _PAD_X - 160, _C_TOP + 18, 160, 30)
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.RIGHT
        r = p.add_run()
        r.text = f"{idx} / {total}"
        r.font.size = Pt(12)
        r.font.color.rgb = C["muted"]
        # 页脚细线：把内容区和页脚分开，翻页时的稳定参照
        line = _box(sl, _PAD_X, _C_TOP, _CANVAS_W - _PAD_X * 2, 1)
        line.fill.solid()
        line.fill.fore_color.rgb = C["muted"]
        line.line.fill.background()

    def _heading(sl, text, color=None):
        """A 区标题：位置与字号全程固定。"""
        accent_bar = _box(sl, _PAD_X, _A_TOP + 52, 6, 34, C["accent"])
        tf = _tb(sl, _PAD_X + 20, _A_TOP + 44, _CANVAS_W - _PAD_X * 2 - 20, 60)
        size = 34 if len(text) <= 16 else (28 if len(text) <= 26 else 23)
        _rich(tf, text, size, color or C["dark"], bold=True, first=True)

    _layouts = layouts_for(detailed[:36])
    prev_layout = ""
    for i, sd in enumerate(detailed[:36]):
        title = str(sd.get("main_title") or sd.get("core_topic") or "幻灯片").strip()
        body = safe_text(sd.get("bullet_points") or sd.get("subtitle") or "")
        lines = [re.sub(r"^\s*(?:[-*•◦▪]|\d+[.、])\s*", "", x).strip()
                 for x in body.split("\n") if x.strip()]
        ptype = sd.get("page_type") or ("cover" if i == 0 else "")
        sl = prs.slides.add_slide(blank)

        # ---------- 封面 ----------
        if ptype == "cover":
            _box(sl, 0, 0, _CANVAS_W, _CANVAS_H, C["dark"])
            _box(sl, 700, 300, 580, 420, C["primary"], MSO_SHAPE.RIGHT_TRIANGLE)
            _place_image(sl, images.get(i), C, box=(700, 150, 500, 460))
            _box(sl, _PAD_X, 250, 90, 6, C["accent"])
            tf = _tb(sl, _PAD_X, 150, 900, 90)
            _rich(tf, title[:24], 56, C["white"], bold=True, first=True)
            if body:
                tf2 = _tb(sl, _PAD_X, 290, 780, 60)
                _rich(tf2, body.replace("\n", "  ")[:90], 18, C["accent"], first=True)
            prev_layout = "cover"
            continue

        # ---------- 目录 ----------
        if ptype == "toc":
            _box(sl, 0, 0, _CANVAS_W, _CANVAS_H, C["light"])
            _heading(sl, title[:20])
            items = [x.strip() for x in re.split(r"[·•｜|\n]+", body) if x.strip()][:6]
            if not items:
                items = [body[:40]] if body else []
            cw = (_CANVAS_W - _PAD_X * 2 - 20 * (len(items) - 1)) // max(len(items), 1)
            for j, it in enumerate(items):
                x = _PAD_X + j * (cw + 20)
                # 大号序号就是这一页的视觉锚点
                card = _box(sl, x, _B_TOP + 30, cw, 300, C["white"])
                card.line.color.rgb = C["secondary"]
                card.line.width = Pt(1)
                tfn = _tb(sl, x + 18, _B_TOP + 48, cw - 36, 60)
                _rich(tfn, f"{j + 1:02d}", 38, C["secondary"], bold=True, first=True)
                tft = _tb(sl, x + 18, _B_TOP + 130, cw - 36, 150)
                _rich(tft, it[:24], 16, C["text"], first=True)
            prev_layout = "toc"
            _footer(sl, i + 1)
            continue

        # ---------- 内容页：按特征选版式 ----------
        layout = _layouts[i]
        if layout == "exercise":
            layout = "cards"
        prev_layout = layout
        _box(sl, 0, 0, _CANVAS_W, _CANVAS_H, C["light"])

        if layout == "formula":
            # 公式页的主角是**公式本身**，不是一句解释。
            # A 区标题只放"这段在讲什么"，式子留给 B 区放大。
            formula = ""
            for cand in [title] + lines:
                if re.search(r"[=＝]", cand):
                    formula = cand
                    break
            if not formula:
                formula = lines[0] if lines else title
            # 「阿基米德原理：F_浮 = ρ_液 g V_排 的定量关系」→ 式子是主角，前后定语剥掉
            if re.search(r"[=＝]", formula):
                core = re.search(r"([^：:]*[=＝][^，。；;]* )", formula)
                head = re.split(r"[：:]", formula, maxsplit=1)
                formula = head[-1].strip() if len(head) > 1 else formula
                formula = re.sub(r"\s*的?(定量关系|关系式|公式|表达式)\s*$", "", formula).strip()
                del core
            _heading(sl, re.split(r"[：:]", title, maxsplit=1)[0][:26])

            # 有配图时公式框让出右侧，图本身是这一页的第二个视觉锚点
            has_img = _place_image(sl, images.get(i), C)
            fw = (int((_CANVAS_W - _PAD_X * 2) * 0.62) if has_img
                  else (_CANVAS_W - _PAD_X * 2))
            fx, fy, fh = _PAD_X, _B_TOP + 16, 150
            fbox = _box(sl, fx, fy, fw, fh, C["white"])
            fbox.line.color.rgb = C["primary"]
            fbox.line.width = Pt(1.5)
            fsize = _fit_size(formula, fw - 60, fh - 40, sizes=(40, 34, 28, 24, 20))
            tff = _tb(sl, fx + 30, fy + (fh - fsize * 1.6) // 2, fw - 60, fh - 30)
            _rich(tff, _clip(formula, fw - 60, fh - 30, fsize), fsize, C["primary"],
                  bold=True, first=True)

            rest = [l for l in lines if l.strip() and l.strip() != formula.strip()][:3]
            ry = fy + fh + 30
            for j, ln in enumerate(rest):
                rh = 54
                if ry + rh > _C_TOP - 10:
                    break
                size = _fit_size(ln, fw - 20, rh - 8, sizes=(18, 17, 16, 15, 14))
                tfl = _tb(sl, fx + 8, ry, fw - 16, rh)
                _rich(tfl, _clip(ln, fw - 16, rh - 8, size), size, C["text"], first=True)
                ry += rh

        elif layout == "compare":
            _heading(sl, title[:26])
            half = (_CANVAS_W - _PAD_X * 2 - 28) // 2
            cols = (lines[:2] + ["", ""])[:2]
            tw = half - 44
            # 卡片高度跟着内容走：固定 400px 配一句短话，下半页就是 70% 空白，
            # 那是"看起来没做完"的主因。
            hs = []
            for col in cols:
                size = _fit_size(col, tw, _B_H - 120, sizes=(22, 20, 18, 17, 16, 15))
                per_line = max(1, int(tw / (size * 1.05)))
                n_lines = max(1, (len(col) + per_line - 1) // per_line)
                hs.append(min(400, max(150, int(n_lines * size * 1.6) + 56)))
            card_h = max(hs) if hs else 200
            for j, col in enumerate(cols):
                x = _PAD_X + j * (half + 28)
                card = _box(sl, x, _B_TOP + 20, half, card_h,
                            C["primary"] if j == 0 else C["white"])
                card.line.color.rgb = C["primary"]
                card.line.width = Pt(1)
                th = card_h - 44
                size = _fit_size(col, tw, th, sizes=(22, 20, 18, 17, 16, 15))
                tc = _tb(sl, x + 22, _B_TOP + 42, tw, th)
                _rich(tc, _clip(col, tw, th, size), size,
                      C["white"] if j == 0 else C["text"], first=True)
            # 多余要点接在卡片下方（此前直接丢弃，等于吞内容）
            ry = _B_TOP + 20 + card_h + 20
            for ln in lines[2:4]:
                if ry + 40 > _C_TOP - 10:
                    break
                size = _fit_size(ln, _CANVAS_W - _PAD_X * 2, 34, sizes=(16, 15, 14))
                tfl = _tb(sl, _PAD_X, ry, _CANVAS_W - _PAD_X * 2, 40)
                _rich(tfl, _clip(ln, _CANVAS_W - _PAD_X * 2, 34, size), size,
                      C["muted"], first=True)
                ry += 40

        elif layout == "cards":
            _heading(sl, title[:26])
            n = min(len(lines), 3) or 1
            cw = (_CANVAS_W - _PAD_X * 2 - 24 * (n - 1)) // n
            tw = cw - 40
            # 同样按内容算高度，并把多出来的要点补在下方
            hs = []
            for ln in lines[:3]:
                size = _fit_size(ln, tw, _B_H - 120, sizes=(20, 18, 17, 16, 15))
                per_line = max(1, int(tw / (size * 1.05)))
                n_lines = max(1, (len(ln) + per_line - 1) // per_line)
                hs.append(min(380, max(150, int(n_lines * size * 1.6) + 56)))
            card_h = max(hs) if hs else 200
            for j, ln in enumerate(lines[:3]):
                x = _PAD_X + j * (cw + 24)
                _box(sl, x, _B_TOP + 24, cw, 8, C["accent"])
                card = _box(sl, x, _B_TOP + 32, cw, card_h, C["white"])
                card.line.color.rgb = C["secondary"]
                card.line.width = Pt(1)
                th = card_h - 44
                size = _fit_size(ln, tw, th, sizes=(20, 18, 17, 16, 15))
                tc = _tb(sl, x + 20, _B_TOP + 54, tw, th)
                _rich(tc, _clip(ln, tw, th, size), size, C["text"], first=True)
            ry = _B_TOP + 32 + card_h + 20
            for ln in lines[3:6]:
                if ry + 38 > _C_TOP - 10:
                    break
                size = _fit_size(ln, _CANVAS_W - _PAD_X * 2, 32, sizes=(16, 15, 14))
                tfl = _tb(sl, _PAD_X, ry, _CANVAS_W - _PAD_X * 2, 38)
                _rich(tfl, _clip(ln, _CANVAS_W - _PAD_X * 2, 32, size), size,
                      C["muted"], first=True)
                ry += 38

        elif layout == "emphasis":
            # 强调页：整页一个大色块 + 一句核心结论（最大号字）
            _box(sl, 0, 0, _CANVAS_W, _CANVAS_H, C["light"])
            block_w = _CANVAS_W - _PAD_X * 2
            text = lines[0] if lines else title
            if _place_image(sl, images.get(i), C):
                block_w = int((_CANVAS_W - _PAD_X * 2) * 0.62)
            _box(sl, _PAD_X, _B_TOP + 16, block_w, 360, C["primary"])
            tw, th = block_w - 88, 250
            size = _fit_size(text, tw, th, sizes=(30, 28, 26, 24, 22, 20))
            tf = _tb(sl, _PAD_X + 44, _B_TOP + 70, tw, th)
            _rich(tf, _clip(text, tw, th, size), size, C["white"], bold=True, first=True)
            tfs = _tb(sl, _PAD_X, _A_TOP + 44, _CANVAS_W - _PAD_X * 2, 50)
            _rich(tfs, _clip(title, _CANVAS_W - _PAD_X * 2, 50, 22), 22,
                  C["accent"], bold=True, first=True)
            ry = _B_TOP + 396
            for ln in lines[1:3]:
                if ry + 44 > _C_TOP - 8:
                    break
                size2 = _fit_size(ln, _CANVAS_W - _PAD_X * 2 - 20, 38, sizes=(16, 15, 14))
                tfl = _tb(sl, _PAD_X + 8, ry, _CANVAS_W - _PAD_X * 2 - 16, 44)
                _rich(tfl, _clip(ln, _CANVAS_W - _PAD_X * 2 - 16, 38, size2), size2,
                      C["text"], first=True)
                ry += 48

        elif layout == "summary":
            _box(sl, 0, 0, _CANVAS_W, _CANVAS_H, C["dark"])
            _box(sl, _PAD_X, _A_TOP + 52, 6, 34, C["accent"])
            tfs = _tb(sl, _PAD_X + 20, _A_TOP + 44, _CANVAS_W - _PAD_X * 2, 60)
            _rich(tfs, title[:26], 34, C["white"], bold=True, first=True)
            n = min(len(lines), 4) or 1
            cw = (_CANVAS_W - _PAD_X * 2 - 20 * (n - 1)) // n
            for j, ln in enumerate(lines[:4]):
                x = _PAD_X + j * (cw + 20)
                _box(sl, x, _B_TOP + 32, cw, 6, C["accent"])
                tw = cw
                th = 260
                size = _fit_size(ln, tw, th, sizes=(17, 16, 15, 14))
                tc = _tb(sl, x, _B_TOP + 60, tw, th)
                _rich(tc, _clip(ln, tw, th, size), size, C["white"], first=True)

        else:  # bullets
            _heading(sl, title[:26])
            _box(sl, _PAD_X, _B_TOP + 24, 5, 430, C["secondary"])
            show = lines[:6]
            avail_h = 420
            tw = _CANVAS_W - _PAD_X * 2 - 60
            # 有配图时正文让出右侧，图本身充当这一页的视觉锚点
            if _place_image(sl, images.get(i), C):
                tw = int((_CANVAS_W - _PAD_X * 2 - 60) * 0.60)
            per_h = max(46, avail_h // max(len(show), 1))
            tf = _tb(sl, _PAD_X + 26, _B_TOP + 24, tw + 34, avail_h)
            # 先把每条的字号定下来，再把剩余高度均摊成段后距 ——
            # 固定 10pt 间距会让 4 条要点只占半页，底部一片白。
            sized = [_fit_size(ln, tw, per_h - 10, sizes=(20, 18, 17, 16, 15)) for ln in show]
            used = sum(s * 1.6 for s in sized)
            gap = max(10.0, (avail_h - used) / max(len(show) - 1, 1))
            for j, ln in enumerate(show):
                size = sized[j]
                para = _rich(tf, _clip(ln, tw, per_h - 10, size),
                             size, C["text"], first=(j == 0))
                para.space_after = Pt(min(gap, 40))

        _footer(sl, i + 1)

    prs.core_properties.title = topic[:50]
    prs.core_properties.subject = "EduForge · 多模态备课智能体"
    prs.save(str(path))


# ---------------------------------------------------------------------------
# 配图：AI 生图 → 本地装饰图 → 无图（三级降级，任何一步失败都不阻塞）
# ---------------------------------------------------------------------------

def image_mode() -> str:
    """配图模式。**默认 `off`**。

    - off ：完全不配图（默认）
    - ai  ：调用通义万相生图（**按张计费，用的是设置页已保存的阿里云 DashScope Key**）
    - deco：只用本地几何装饰图（零成本，但只是色块，不是教学示意图）

    为什么默认是 off 而不是 ai：生图会**真实消耗用户账号的额度**，
    在用户没有明确启用的情况下替他花钱是不可接受的。要用必须显式开启。
    """
    import os
    m = (os.getenv("EDUFORGE_PPT_IMAGE_MODE") or "off").strip().lower()
    return m if m in ("off", "ai", "deco") else "off"


def _max_images() -> int:
    """单次生成最多生几张图。

    为什么限量：官方 QPS 2 / 并发 1，单张 10–30 秒，且**按张计费**。
    一份 15 页课件全生图既慢又贵，教师也未必需要 —— 封面加两三个
    核心概念页就足够撑起观感。
    """
    import os
    try:
        return max(0, min(6, int(os.getenv("EDUFORGE_PPT_IMAGE_MAX", "2"))))
    except Exception:
        return 2


# 会插配图的版式。配图必须跟着**最终版式**走 —— 否则给卡片页配了图也用不上，
# 白白多花一次生成（AI 生图是按张计费的）。
IMAGE_FRIENDLY_LAYOUTS = ("cover", "bullets", "emphasis", "formula")


def layouts_for(detailed: List[Dict[str, Any]]) -> List[str]:
    """一次性算出每页版式，供渲染与配图共用。

    为什么要提出来：版式是渲染决策，配图必须服从它。两边各算一遍不仅可能不一致，
    还会给"根本不插图"的版式白白生图。
    """
    import re as _re
    out: List[str] = []
    prev = ""
    for i, sd in enumerate(detailed):
        ptype = sd.get("page_type") or ("cover" if i == 0 else "")
        if ptype in ("cover", "toc"):
            lay = ptype
        elif ptype == "exercise":
            lay = "cards"
        elif ptype == "summary":
            lay = "summary"
        else:
            title = str(sd.get("main_title") or sd.get("core_topic") or "")
            body = safe_text(sd.get("bullet_points") or sd.get("subtitle") or "")
            lines = [_re.sub(r"^\s*(?:[-*•◦▪]|\d+[.、])\s*", "", x).strip()
                     for x in body.split("\n") if x.strip()]
            lay = _pick_layout(i, prev, title, lines)
        out.append(lay)
        prev = lay
    return out


def prepare_images(topic: str, detailed: List[Dict[str, Any]], theme_color: str,
                   subject: str, api_key: str = "") -> Dict[int, str]:
    """为若干页准备配图，返回 {页索引: 本地路径}。

    降级链（关键设计）：
      1. AI 生图（限量，串行，带超时）
      2. 本地装饰图（Pillow 绘制，零成本）
      3. 不配图
    **任何一步失败都必须继续**，配图失败绝不能让整份 PPT 生成失败 ——
    那是"教师等了半天，最后什么都拿不到"的事故。
    """
    out: Dict[int, str] = {}
    mode = image_mode()
    if mode == "off":
        return out

    # 挑值得配图的页：封面 + 内容/概念页。
    # 目录页与练习页不插图（目录是条目列表，练习页配图没意义），
    # 选了也用不上，白白浪费一次生成。
    lays = layouts_for(detailed)
    candidates = [i for i, lay in enumerate(lays) if lay in IMAGE_FRIENDLY_LAYOUTS]

    limit = _max_images()
    # 装饰图是本地绘制，零成本 —— 可以多配几页，让版面不至于只有封面一张图
    if mode == "deco":
        limit = min(6, max(limit, 4))
    picked = ([0] if 0 in candidates else []) + [i for i in candidates if i != 0][:max(0, limit - (1 if 0 in candidates else 0))]

    used_ai = 0
    for i in picked:
        sd = detailed[i]
        core = str(sd.get("core_topic") or sd.get("main_title") or topic)
        if mode == "ai" and api_key and used_ai < limit:
            try:
                from .services import image_gen
                prompt = image_gen.build_prompt(topic, subject, core)
                path = image_gen.generate(prompt, api_key)
                if path:
                    out[i] = path
                    used_ai += 1
                    continue
            except Exception:
                pass  # 落到本地装饰图

        # 兜底：本地几何装饰图。
        # 不用 services/image_service —— 它在图上渲染中文会 segfault（见 image_gen 注释）。
        try:
            from .services import image_gen
            p = image_gen.decorative(topic=core, subject=subject or "general")
            if p:
                out[i] = p
        except Exception:
            continue
    return out


def _place_image(sl, path, C, box: "tuple | None" = None) -> bool:
    """把配图放到内容区右侧；成功返回 True（调用方据此收窄文本区）。

    为什么放在右侧而不是当背景：背景图会压低文字对比度，课堂上后排看不清。
    右侧竖图既能当视觉锚点，又不抢正文。
    """
    if not path:
        return False
    try:
        import os
        if not os.path.exists(path):
            return False
        from pptx.util import Pt as _Pt
        if box:
            x, y, w, h = box
        else:
            x, y, w, h = (_CANVAS_W - _PAD_X - 400, _B_TOP + 20, 400, 430)
        pic = sl.shapes.add_picture(
            path, _px(x), _px(y), width=_px(w), height=_px(h))
        pic.line.color.rgb = C["secondary"]
        pic.line.width = _Pt(1)
        return True
    except Exception:
        # 配图失败绝不能让整页生成失败
        return False


# `F_浮` / `ρ_液` / `cm³` / `10^3` → (基础, 下标, 上标)
_SCRIPT_RE = re.compile(
    r"(?P<base>[^\s_^]+?)(?:_(?P<sub>[一-龥A-Za-z0-9]+)|\^(?P<sup>-?\d+))?"
)
_SUP_CHARS = {"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
              "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9"}


def _split_script(text: str) -> List[tuple]:
    """把一行文本切成 [(基础, 下标, 上标), …]，供上下标排版使用。

    为什么值得单独做：物理/化学方程式在课件里是刚需。写成 `F_浮`、`cm³`
    这样的纯文本，投影到教室后排就是一团糊 —— 下标必须真的下沉。
    """
    out: List[tuple] = []
    buf = ""
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "_" and i + 1 < n:
            nxt = text[i + 1]
            if re.match(r"[一-龥A-Za-z0-9]", nxt):
                j = i + 1
                # 下标最多取 2 个字符：贪婪匹配会把 `F_浮线性变化` 的
                # 「浮线性变化」整串吞成下标（实测把正文字都压扁了）。
                # 物理量下标（浮/液/排/物）本来就是 1~2 字。
                # 中文下标几乎都是单字（浮/液/排/物）；连读两个会把正文吞掉。
                # 英文/数字下标才允许多字符（如 m_water）。
                limit = 1 if re.match(r"[一-龥]", nxt) else 4
                while j < n and re.match(r"[一-龥A-Za-z0-9]", text[j]) and (j - (i + 1)) < limit:
                    j += 1
                out.append((buf, text[i + 1:j], ""))
                buf = ""
                i = j
                continue
        if ch == "^" and i + 1 < n and text[i + 1].isdigit():
            j = i + 1
            while j < n and text[j].isdigit():
                j += 1
            out.append((buf, "", text[i + 1:j]))
            buf = ""
            i = j
            continue
        if ch in _SUP_CHARS:
            if buf:
                out.append((buf, "", ""))
                buf = ""
            out.append(("", "", _SUP_CHARS[ch]))
            i += 1
            continue
        buf += ch
        i += 1
    if buf:
        out.append((buf, "", ""))
    return out or [(text, "", "")]


def _run(tid: str, body: Dict[str, Any]) -> None:
    try:
        topic = body.get("topic") or "课程"
        audience = body.get("audience") or body.get("target_audience") or "学生"
        theme_color = body.get("theme_color") or "蓝色系"
        style_pref = body.get("style_preference") or body.get("template") or "标准"
        kps = body.get("key_points") or []
        if isinstance(kps, str):
            kps = [kps]
        kp_txt = "\n".join(str(x) for x in kps[:12])

        _update(tid, status="generating", progress=5, current_step="正在生成教学大纲")
        time.sleep(0.15)

        prompt = (
            f"你是资深教学设计专家。请为主题「{topic}」设计课堂 PPT 结构。\n"
            f"教学对象：{audience}。\n"
            f"版式风格偏好：{style_pref}；主题色系：{theme_color}。\n"
        )
        if kp_txt:
            prompt += f"必须覆盖的知识点：\n{kp_txt}\n"
        prompt += (
            "请输出 8~12 行，每行一个幻灯片标题（不要编号），涵盖："
            "导入、目标/目录、核心概念（可多页）、例题或活动、课堂练习、小结、作业或延伸。"
        )

        outline = llm_client.blocking_chat([{"role": "user", "content": prompt}], max_tokens=1200)
        if not outline or len(outline.strip()) < 8:
            outline = (
                f"{topic} — 课程导入\n学习目标与重点\n核心概念一\n核心概念二\n"
                "典型例题\n课堂练习\n易错点辨析\n课堂小结\n拓展与作业"
            )

        _update(tid, progress=40, current_step="正在生成幻灯片与版式")
        time.sleep(0.1)
        detailed = _build_detailed_content(topic, outline, audience)

        safe = re.sub(r'[<>:"/\\|?*]', "_", topic[:36]) + "_" + tid[:10]
        task_dir = GENERATED_CW / safe
        task_dir.mkdir(parents=True, exist_ok=True)
        fn = re.sub(r'[<>:"/\\|?*]', "_", topic[:40] or "courseware") + ".pptx"
        pptx_path = task_dir / fn

        _update(tid, progress=62, current_step="正在准备配图")
        try:
            from .persist import get_active_llm_settings
            _key = get_active_llm_settings().get("api_key") or ""
        except Exception:
            _key = ""
        images = prepare_images(topic, detailed, theme_color, detected_subject, _key)
        if images:
            _update(tid, progress=68, current_step=f"已为 {len(images)} 页配图")

        _update(tid, progress=70, current_step="正在写入 PPTX 文件")
        _write_pptx(pptx_path, topic, detailed, theme_color, images)

        rel_dir = f"generated_courseware/{task_dir.name}".replace("\\", "/")
        result = {
            "topic": topic,
            "task_id": tid,
            "task_dir": str(task_dir),
            "ppt_content": {
                "detailed_content": detailed,
                "outline": outline,
                "theme": theme_color,
                "style": style_pref,
            },
            "files": {
                "pptx": f"/{rel_dir}/{pptx_path.name}",
            },
        }
        _update(
            tid,
            status="completed",
            progress=100,
            current_step="完成",
            result=result,
        )
    except Exception as e:
        _update(tid, status="failed", error=str(e), progress=0)


def start_task(body: Dict[str, Any]) -> str:
    tid = "ppt_" + uuid.uuid4().hex[:12]
    with _lock:
        TASKS[tid] = {
            "status": "pending",
            "progress": 0,
            "current_step": "排队中",
            "result": None,
            "error": None,
        }
    threading.Thread(target=_run, args=(tid, body), daemon=True).start()
    return tid


def get_status(tid: str) -> Optional[Dict[str, Any]]:
    with _lock:
        t = TASKS.get(tid)
        if not t:
            return None
        return dict(t)
