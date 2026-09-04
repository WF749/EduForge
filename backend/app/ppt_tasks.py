"""Background PPT generation tasks (polled by /ppt/status)."""
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import llm_client
from .paths import GENERATED_CW

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

    # 添加互动练习页
    slides.append(
        {
            "page_num": n,
            "page_type": "exercise",
            "core_topic": "课堂互动练习",
            "main_title": f"{topic} - 课堂练习",
            "bullet_points": (
                f"• 选择题：关于{topic}的核心概念\n"
                f"• 填空题：{topic}的关键要点\n"
                f"• 思考题：{topic}的实际应用\n"
                f"• 讨论题：{topic}的拓展思考"
            ),
        }
    )
    n += 1

    # 添加总结页
    slides.append(
        {
            "page_num": n,
            "page_type": "summary",
            "core_topic": "课堂小结",
            "main_title": "总结与延伸",
            "bullet_points": (
                f"• {topic}核心要点回顾\n"
                f"• 学习目标达成检验\n"
                f"• 课后作业布置\n"
                f"• 拓展学习建议"
            ),
        }
    )

    return slides


def _write_pptx(path: Path, topic: str, detailed: List[Dict[str, Any]], theme_name: str) -> None:
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Pt

    prs = Presentation()
    rgb = _theme_rgb(theme_name)
    accent = RGBColor(*rgb)

    layouts = prs.slide_layouts
    layout_title = layouts[0] if len(layouts) > 0 else layouts[0]
    layout_content = layouts[1] if len(layouts) > 1 else layouts[0]

    for i, slide in enumerate(detailed[:36]):
        is_cover = slide.get("page_type") == "cover" or i == 0
        layout = layout_title if is_cover else layout_content
        s = prs.slides.add_slide(layout)
        title = slide.get("main_title") or slide.get("core_topic") or "幻灯片"
        if s.shapes.title:
            s.shapes.title.text = title
            tf = s.shapes.title.text_frame
            tf.paragraphs[0].font.size = Pt(32 if is_cover else 28)
            tf.paragraphs[0].font.bold = True
            try:
                tf.paragraphs[0].font.color.rgb = accent
            except Exception:
                pass
        sub = slide.get("subtitle") or slide.get("bullet_points") or ""
        if len(s.placeholders) > 1 and sub:
            tf = s.placeholders[1].text_frame
            tf.text = sub[:4500]
            for p in tf.paragraphs:
                p.font.size = Pt(18 if is_cover else 16)
                p.alignment = PP_ALIGN.LEFT
        elif sub and s.shapes.title and not is_cover:
            # title-only layout: append subtitle below via textbox if possible
            pass

    prs.core_properties.title = topic[:50]
    prs.core_properties.subject = "Multimodal AI Teaching Agent"
    prs.save(str(path))


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

        _update(tid, progress=70, current_step="正在写入 PPTX 文件")
        _write_pptx(pptx_path, topic, detailed, theme_color)

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
