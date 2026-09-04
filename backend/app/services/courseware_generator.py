"""课件生成服务 - 生成高质量PPTX和DOCX文件"""
import os
import json
import uuid
import re
from typing import Optional, Dict, List
from datetime import datetime
from .llm_service import llm_service
from .teaching_strategy_service import teaching_strategy_service

# 尝试导入文档生成库
try:
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RgbColor
    from pptx.enum.text import PP_ALIGN
    from pptx.enum.shapes import MSO_SHAPE
    PPTX_AVAILABLE = True
except ImportError:
    PPTX_AVAILABLE = False

try:
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False


class CoursewareGenerator:
    """课件生成器类 - 生成高质量PPTX和DOCX文件"""

    def __init__(self, output_dir: str = "generated_courseware"):
        """初始化课件生成器"""
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        # 模板配置
        self.templates = {
            "standard": {
                "name": "标准教学模板",
                "description": "适合一般课程的标准模板，包含课程介绍、主要内容、总结和作业",
                "structure": ["封面页", "目录页", "课程目标", "主要内容", "互动环节", "总结页", "参考资料"]
            },
            "interactive": {
                "name": "互动教学模板",
                "description": "强调互动和讨论的教学模板，包含小组活动和案例分析",
                "structure": ["封面页", "目录页", "课程目标", "小组讨论", "案例分析", "互动游戏", "总结页", "参考资料"]
            },
            "experimental": {
                "name": "实验教学模板",
                "description": "适合实验课程的模板，包含实验目的、步骤和结果分析",
                "structure": ["封面页", "目录页", "实验目的", "实验原理", "实验步骤", "数据分析", "实验结论", "参考资料"]
            },
            "lecture": {
                "name": "学术讲座模板",
                "description": "适合学术讲座的模板，包含研究背景、方法和结论",
                "structure": ["封面页", "目录页", "研究背景", "研究方法", "研究结果", "讨论分析", "结论展望", "参考资料"]
            }
        }

        # 主题色配置
        self.theme_colors = {
            "蓝色系": {
                "primary": (52, 152, 219),
                "secondary": (41, 128, 185),
                "text": (44, 62, 80),
                "background": (255, 255, 255)
            },
            "绿色系": {
                "primary": (46, 204, 113),
                "secondary": (39, 174, 96),
                "text": (26, 188, 156),
                "background": (255, 255, 255)
            },
            "红色系": {
                "primary": (231, 76, 60),
                "secondary": (192, 57, 43),
                "text": (155, 89, 182),
                "background": (255, 255, 255)
            },
            "紫色系": {
                "primary": (155, 89, 182),
                "secondary": (142, 68, 173),
                "text": (123, 31, 162),
                "background": (255, 255, 255)
            },
            "橙色系": {
                "primary": (241, 196, 15),
                "secondary": (243, 156, 18),
                "text": (211, 84, 0),
                "background": (255, 255, 255)
            }
        }

        # 课时时长与PPT页数对应规则
        self.duration_page_rules = {
            15: {"min": 5, "max": 8, "pages": ["封面页", "目录页", "核心知识点页(2-4页)", "总结页", "作业页"]},
            30: {"min": 8, "max": 12, "pages": ["封面页", "目录页", "知识点页(4-6页)", "案例页", "习题页", "总结页", "作业页"]},
            45: {"min": 10, "max": 15, "pages": ["封面页", "目录页", "导入页", "知识点页(5-8页)", "案例分析页", "互动习题页", "总结页", "拓展页", "作业页"]},
            60: {"min": 15, "max": 20, "pages": ["封面页", "目录页", "导入页", "知识点页(8-12页)", "多案例页", "互动习题页", "课堂讨论页", "总结页", "拓展页", "作业页"]},
            90: {"min": 20, "max": 28, "pages": ["封面页", "目录页", "2个模块的知识点拆解", "多案例", "实验/研讨环节", "习题", "总结", "拓展", "作业"]}
        }

    def generate(self, topic: str, duration: int, audience: str, format: str,
                 provider: Optional[str] = None, template: str = "standard",
                 subject: str = "general", theme_color: str = "蓝色系",
                 key_points: list = None, reference_docs: list = None):
        """生成课件 - 同时生成PPTX和DOCX文件"""
        # 设置提供商
        if provider:
            llm_service.set_provider(provider)

        # 生成唯一ID和目录
        task_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        task_dir = os.path.join(self.output_dir, f"{topic}_{timestamp}_{task_id}")
        os.makedirs(task_dir, exist_ok=True)

        # 根据目标受众确定教学风格
        teaching_style = self._determine_teaching_style(audience)

        # 分析需求
        requirements = self.analyze_requirements(topic, audience, duration, key_points, reference_docs, subject)

        # 教学策略智能体分析 - 注入学科和学段特定策略
        try:
            strategy_analysis = teaching_strategy_service.analyze_teaching_scene(
                topic=topic, audience=audience, subject=subject, duration=duration
            )
            strategy_prompt = teaching_strategy_service.get_strategy_prompt_injection(
                topic=topic, audience=audience, subject=subject, duration=duration
            )
            requirements["teaching_strategy"] = strategy_analysis
            requirements["strategy_prompt"] = strategy_prompt
        except Exception as e:
            print(f"教学策略分析跳过: {e}")
            requirements["teaching_strategy"] = {}
            requirements["strategy_prompt"] = ""

        # 生成PPT大纲
        ppt_outline = self.generate_ppt_outline(requirements)

        # 生成详细内容
        detailed_content = self.generate_detailed_content(ppt_outline, requirements)

        # 生成教案内容（注入教学策略）
        strategy_prompt = requirements.get("strategy_prompt", "")
        lesson_plan = self._generate_lesson_plan(topic, duration, audience, subject, teaching_style, strategy_prompt)

        # 生成动画创意
        animation_ideas = self._generate_animation_ideas(topic, lesson_plan, subject, audience, teaching_style, duration)

        # 生成互动游戏
        interactive_games = self._generate_interactive_games(topic, audience, lesson_plan, teaching_style)

        # 生成真实的PPTX和DOCX文件
        files = {}

        if PPTX_AVAILABLE:
            pptx_path = self._create_pptx(topic, duration, audience, detailed_content, teaching_style, task_dir, theme_color, template)
            if pptx_path:
                files['pptx'] = pptx_path

        if DOCX_AVAILABLE:
            docx_path = self._create_docx(topic, duration, audience, lesson_plan, interactive_games, animation_ideas, teaching_style, task_dir)
            if docx_path:
                files['docx'] = docx_path

        # 保存生成数据
        data_path = os.path.join(task_dir, "courseware_data.json")
        with open(data_path, 'w', encoding='utf-8') as f:
            json.dump({
                "topic": topic,
                "duration": duration,
                "audience": audience,
                "template": template,
                "subject": subject,
                "theme_color": theme_color,
                "key_points": key_points,
                "reference_docs": reference_docs,
                "teaching_style": teaching_style,
                "lesson_plan": lesson_plan,
                "ppt_outline": ppt_outline,
                "detailed_content": detailed_content,
                "animation_ideas": animation_ideas,
                "interactive_games": interactive_games,
                "teaching_strategy": requirements.get("teaching_strategy", {}),
                "files": files
            }, f, ensure_ascii=False, indent=2)

        return {
            "task_id": task_id,
            "topic": topic,
            "duration": duration,
            "audience": audience,
            "template": template,
            "subject": subject,
            "theme_color": theme_color,
            "key_points": key_points,
            "reference_docs": reference_docs,
            "teaching_style": teaching_style,
            "lesson_plan": lesson_plan,
            "ppt_outline": ppt_outline,
            "detailed_content": detailed_content,
            "animation_ideas": animation_ideas,
            "interactive_games": interactive_games,
            "teaching_strategy": requirements.get("teaching_strategy", {}),
            "files": files,
            "task_dir": task_dir
        }

    def _create_pptx(self, topic: str, duration: int, audience: str,
                     detailed_content: list, teaching_style: dict, task_dir: str, theme_color: str = "蓝色系", template: str = "standard") -> Optional[str]:
        """创建PPTX文件"""
        try:
            from pptx import Presentation
            from pptx.util import Inches, Pt
            from pptx.dml.color import RGBColor as RgbColor
            from pptx.enum.text import PP_ALIGN
            from pptx.enum.shapes import MSO_SHAPE
            
            prs = Presentation()
            prs.slide_width = Inches(13.333)
            prs.slide_height = Inches(7.5)

            # 获取主题色
            theme_color_config = self.theme_colors.get(theme_color, self.theme_colors["蓝色系"])
            primary_color = RgbColor(*theme_color_config["primary"])
            secondary_color = RgbColor(*theme_color_config["secondary"])
            text_color = RgbColor(*theme_color_config["text"])

            # 根据详细内容生成PPT
            for page_content in detailed_content:
                page_type = page_content.get("page_type")
                if page_type == "cover":
                    self._add_cover_slide(prs, page_content, primary_color, secondary_color, text_color)
                elif page_type == "toc":
                    self._add_toc_slide(prs, page_content, text_color, primary_color)
                elif page_type == "knowledge":
                    self._add_knowledge_slide(prs, page_content, text_color, primary_color)
                elif page_type == "exercise":
                    self._add_exercise_slide(prs, page_content, text_color, primary_color)
                elif page_type == "summary":
                    self._add_summary_slide(prs, page_content, text_color, primary_color)
                elif page_type == "extension":
                    self._add_extension_slide(prs, page_content, text_color, primary_color)

            # 保存
            filename = f"{self._clean_filename(topic)}_课件.pptx"
            filepath = os.path.join(task_dir, filename)
            prs.save(filepath)
            return filepath

        except Exception as e:
            print(f"创建PPTX失败: {e}")
            return None

    def _add_cover_slide(self, prs, page_content: dict, primary_color, secondary_color, text_color):
        """封面页"""
        slide = prs.slides.add_slide(prs.slide_layouts[6])

        # 背景
        shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
        shape.fill.solid()
        shape.fill.fore_color.rgb = primary_color
        shape.line.fill.background()

        # 装饰
        shape2 = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(9.5), Inches(-1), Inches(5), Inches(5))
        shape2.fill.solid()
        shape2.fill.fore_color.rgb = secondary_color
        shape2.line.fill.background()

        # 主标题
        title_box = slide.shapes.add_textbox(Inches(0.8), Inches(2.5), Inches(11), Inches(1.5))
        tf = title_box.text_frame
        p = tf.paragraphs[0]
        p.text = page_content.get("main_title", "未命名课程")
        p.font.size = Pt(54)
        p.font.bold = True
        p.font.color.rgb = RgbColor(255, 255, 255)
        p.alignment = PP_ALIGN.CENTER

        # 副标题
        subtitle_box = slide.shapes.add_textbox(Inches(0.8), Inches(4.2), Inches(11), Inches(1))
        tf = subtitle_box.text_frame
        p = tf.paragraphs[0]
        p.text = page_content.get("subtitle", "")
        p.font.size = Pt(24)
        p.font.color.rgb = RgbColor(255, 255, 255)
        p.alignment = PP_ALIGN.CENTER

        # 授课人信息
        instructor_info = page_content.get("instructor_info", "授课教师")
        instructor_box = slide.shapes.add_textbox(Inches(0.8), Inches(5.2), Inches(11), Inches(0.5))
        tf = instructor_box.text_frame
        p = tf.paragraphs[0]
        p.text = instructor_info
        p.font.size = Pt(20)
        p.font.color.rgb = RgbColor(255, 255, 255)
        p.alignment = PP_ALIGN.CENTER

        # 日期
        date_box = slide.shapes.add_textbox(Inches(0.8), Inches(5.8), Inches(11), Inches(0.5))
        tf = date_box.text_frame
        p = tf.paragraphs[0]
        p.text = datetime.now().strftime("%Y年%m月%d日")
        p.font.size = Pt(18)
        p.font.color.rgb = RgbColor(255, 255, 255)
        p.alignment = PP_ALIGN.CENTER

    def _add_toc_slide(self, prs, page_content: dict, text_color, primary_color):
        """目录页"""
        slide = prs.slides.add_slide(prs.slide_layouts[6])

        # 顶部色条
        shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(0.1))
        shape.fill.solid()
        shape.fill.fore_color.rgb = primary_color
        shape.line.fill.background()

        # 标题
        title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.5), Inches(11), Inches(1))
        tf = title_box.text_frame
        p = tf.paragraphs[0]
        p.text = page_content.get("core_topic", "目录")
        p.font.size = Pt(44)
        p.font.bold = True
        p.font.color.rgb = text_color

        # 目录项
        toc_items = page_content.get("toc_items", [])

        y = 2.0
        for i, item in enumerate(toc_items):
            item_box = slide.shapes.add_textbox(Inches(2), Inches(y), Inches(9), Inches(0.8))
            tf = item_box.text_frame
            p = tf.paragraphs[0]
            p.text = f"{i+1}. {item}"
            p.font.size = Pt(24)
            p.font.color.rgb = text_color
            y += 0.9

    def _add_knowledge_slide(self, prs, page_content: dict, text_color, primary_color):
        """知识点页"""
        slide = prs.slides.add_slide(prs.slide_layouts[6])

        # 顶部色条
        shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(0.1))
        shape.fill.solid()
        shape.fill.fore_color.rgb = primary_color
        shape.line.fill.background()

        # 标题
        title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.4), Inches(12), Inches(1))
        tf = title_box.text_frame
        p = tf.paragraphs[0]
        p.text = page_content.get('core_topic', '知识点')
        p.font.size = Pt(36)
        p.font.bold = True
        p.font.color.rgb = text_color

        # 核心要点
        key_points = page_content.get('key_points', [])
        if key_points:
            content_box = slide.shapes.add_textbox(Inches(0.8), Inches(1.5), Inches(11.5), Inches(4))
            tf = content_box.text_frame
            tf.word_wrap = True

            for i, point in enumerate(key_points):
                if i == 0:
                    p = tf.paragraphs[0]
                else:
                    p = tf.add_paragraph()
                p.text = f"• {point}"
                p.font.size = Pt(20)
                p.font.color.rgb = text_color
                p.space_after = Pt(12)

        # 案例分析
        case_study = page_content.get('case_study', '')
        if case_study:
            case_box = slide.shapes.add_textbox(Inches(0.8), Inches(5), Inches(11.5), Inches(2))
            tf = case_box.text_frame
            tf.word_wrap = True

            # 案例标题
            p = tf.paragraphs[0]
            p.text = "案例分析"
            p.font.size = Pt(20)
            p.font.bold = True
            p.font.color.rgb = primary_color
            p.space_after = Pt(6)

            # 案例内容
            p = tf.add_paragraph()
            p.text = case_study
            p.font.size = Pt(16)
            p.font.color.rgb = text_color

    def _add_summary_slide(self, prs, page_content: dict, text_color, primary_color):
        """总结页"""
        slide = prs.slides.add_slide(prs.slide_layouts[6])

        # 顶部色条
        shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(0.1))
        shape.fill.solid()
        shape.fill.fore_color.rgb = primary_color
        shape.line.fill.background()

        # 标题
        title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.5), Inches(12), Inches(1))
        tf = title_box.text_frame
        p = tf.paragraphs[0]
        p.text = page_content.get("core_topic", "课程总结")
        p.font.size = Pt(40)
        p.font.bold = True
        p.font.color.rgb = text_color

        # 核心知识点复盘
        knowledge_review = page_content.get("knowledge_review", [])
        if not isinstance(knowledge_review, list):
            knowledge_review = [knowledge_review]

        y = 1.8
        for item in knowledge_review:
            item_box = slide.shapes.add_textbox(Inches(1.5), Inches(y), Inches(10), Inches(0.8))
            tf = item_box.text_frame
            p = tf.paragraphs[0]
            p.text = f"✓  {item}"
            p.font.size = Pt(20)
            p.font.color.rgb = text_color
            y += 0.8

        # 学习目标完成情况
        goals_achievement = page_content.get("goals_achievement", "")
        if goals_achievement:
            goals_box = slide.shapes.add_textbox(Inches(1.5), Inches(y), Inches(10), Inches(0.8))
            tf = goals_box.text_frame
            p = tf.paragraphs[0]
            p.text = f"✓  {goals_achievement}"
            p.font.size = Pt(20)
            p.font.color.rgb = text_color
            y += 0.8

        # 课后作业
        homework = page_content.get("homework", "")
        if homework:
            hw_box = slide.shapes.add_textbox(Inches(1.5), Inches(y), Inches(10), Inches(1))
            tf = hw_box.text_frame
            p = tf.paragraphs[0]
            p.text = f"课后作业：{homework}"
            p.font.size = Pt(18)
            p.font.color.rgb = text_color

    def _add_exercise_slide(self, prs, page_content: dict, text_color, primary_color):
        """互动习题页"""
        slide = prs.slides.add_slide(prs.slide_layouts[6])

        # 顶部色条
        shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(0.1))
        shape.fill.solid()
        shape.fill.fore_color.rgb = primary_color
        shape.line.fill.background()

        # 标题
        title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.4), Inches(12), Inches(1))
        tf = title_box.text_frame
        p = tf.paragraphs[0]
        p.text = page_content.get("core_topic", "互动练习")
        p.font.size = Pt(36)
        p.font.bold = True
        p.font.color.rgb = text_color

        # 习题内容
        exercises = page_content.get("exercises", [])
        if exercises:
            content_box = slide.shapes.add_textbox(Inches(0.8), Inches(1.5), Inches(11.5), Inches(5))
            tf = content_box.text_frame
            tf.word_wrap = True

            for i, exercise in enumerate(exercises):
                # 题目
                p = tf.add_paragraph()
                p.text = f"{i+1}. {exercise.get('question', '')}"
                p.font.size = Pt(20)
                p.font.bold = True
                p.font.color.rgb = text_color
                p.space_after = Pt(8)

                # 选项
                options = exercise.get('options', [])
                for j, option in enumerate(options):
                    p = tf.add_paragraph()
                    p.text = f"   {chr(65+j)}. {option}"
                    p.font.size = Pt(18)
                    p.font.color.rgb = text_color
                    p.space_after = Pt(4)

                # 答案
                answer = exercise.get('answer', '')
                p = tf.add_paragraph()
                p.text = f"答案：{answer}"
                p.font.size = Pt(18)
                p.font.bold = True
                p.font.color.rgb = primary_color
                p.space_after = Pt(12)

    def _add_extension_slide(self, prs, page_content: dict, text_color, primary_color):
        """拓展页"""
        slide = prs.slides.add_slide(prs.slide_layouts[6])

        # 顶部色条
        shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(0.1))
        shape.fill.solid()
        shape.fill.fore_color.rgb = primary_color
        shape.line.fill.background()

        # 标题
        title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.4), Inches(12), Inches(1))
        tf = title_box.text_frame
        p = tf.paragraphs[0]
        p.text = page_content.get("core_topic", "拓展资源")
        p.font.size = Pt(36)
        p.font.bold = True
        p.font.color.rgb = text_color

        # 拓展内容
        after_class_thoughts = page_content.get("after_class_thoughts", [])
        if not isinstance(after_class_thoughts, list):
            after_class_thoughts = [after_class_thoughts]

        y = 1.8
        for item in after_class_thoughts:
            item_box = slide.shapes.add_textbox(Inches(1.5), Inches(y), Inches(10), Inches(0.8))
            tf = item_box.text_frame
            p = tf.paragraphs[0]
            p.text = f"• {item}"
            p.font.size = Pt(20)
            p.font.color.rgb = text_color
            y += 0.8

    def _add_thank_you_slide(self, prs):
        """感谢页"""
        slide = prs.slides.add_slide(prs.slide_layouts[6])

        # 背景
        shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
        shape.fill.solid()
        shape.fill.fore_color.rgb = RgbColor(44, 62, 80)
        shape.line.fill.background()

        # 感谢文字
        title_box = slide.shapes.add_textbox(Inches(0.5), Inches(3), Inches(12), Inches(1.5))
        tf = title_box.text_frame
        p = tf.paragraphs[0]
        p.text = "感谢聆听"
        p.font.size = Pt(72)
        p.font.bold = True
        p.font.color.rgb = RgbColor(255, 255, 255)
        p.alignment = PP_ALIGN.CENTER

        # 副标题
        subtitle_box = slide.shapes.add_textbox(Inches(0.5), Inches(4.5), Inches(12), Inches(1))
        tf = subtitle_box.text_frame
        p = tf.paragraphs[0]
        p.text = "欢迎提问与交流"
        p.font.size = Pt(28)
        p.font.color.rgb = RgbColor(189, 195, 199)
        p.alignment = PP_ALIGN.CENTER

    def _parse_ppt_content(self, ppt_content: str) -> List[dict]:
        """解析PPT内容"""
        slides = []

        # 尝试多种格式解析
        if '页面标题' in ppt_content or '页标题' in ppt_content:
            sections = re.split(r'(?:页面标题|页标题)\s*[:：]', ppt_content)
            for i, section in enumerate(sections[1:], 1):
                lines = section.strip().split('\n')
                title = lines[0].strip() if lines else f'内容{i}'
                content = '\n'.join(lines[1:]).strip()
                slides.append({'title': title, 'content': content})
        elif '\n\n' in ppt_content:
            sections = ppt_content.split('\n\n')
            for i, section in enumerate(sections):
                lines = section.strip().split('\n')
                if lines:
                    title = lines[0].strip()
                    content = '\n'.join(lines[1:]).strip() if len(lines) > 1 else section.strip()
                    slides.append({'title': title, 'content': content})
        else:
            # 默认内容
            slides.append({'title': '课程导入', 'content': '通过实例引入课程主题'})
            slides.append({'title': '核心概念', 'content': '讲解主要知识点'})
            slides.append({'title': '案例分析', 'content': '结合实际案例加深理解'})
            slides.append({'title': '实践应用', 'content': '课堂练习与应用'})

        return slides[:10]  # 限制最多10页

    def _create_docx(self, topic: str, duration: int, audience: str,
                    lesson_plan: str, interactive_games: str, animation_ideas: str,
                    teaching_style: dict, task_dir: str) -> Optional[str]:
        """创建DOCX文件"""
        try:
            from docx import Document
            from docx.shared import Inches, Pt, RGBColor
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            doc = Document()

            # 标题
            title = doc.add_heading(topic, 0)
            title.alignment = WD_ALIGN_PARAGRAPH.CENTER

            # 基本信息
            doc.add_heading('课程基本信息', 1)
            info_table = doc.add_table(rows=4, cols=2)
            info_table.style = 'Table Grid'
            info_data = [
                ('课程主题', topic),
                ('目标受众', audience),
                ('课程时长', f'{duration}分钟'),
                ('教学风格', teaching_style.get('style', '通用'))
            ]
            for i, (label, value) in enumerate(info_data):
                info_table.rows[i].cells[0].text = label
                info_table.rows[i].cells[1].text = value

            doc.add_paragraph()

            # 教案内容
            doc.add_heading('教案内容', 1)
            self._add_docx_text(doc, lesson_plan)

            # 互动游戏
            if interactive_games:
                doc.add_heading('互动游戏设计', 1)
                self._add_docx_text(doc, interactive_games)

            # 动画创意
            if animation_ideas:
                doc.add_heading('动画创意方案', 1)
                self._add_docx_text(doc, animation_ideas)

            # 教学反思
            doc.add_heading('教学反思', 1)
            reflections = [
                '本节课的成功之处：教学目标达成情况、学生参与度分析',
                '需要改进的地方：教学内容调整建议、时间安排优化',
                '下次课的改进计划：针对学生反馈的调整、增加互动环节'
            ]
            for item in reflections:
                p = doc.add_paragraph(item)
                p.paragraph_format.space_after = Pt(6)

            # 保存
            filename = f"{self._clean_filename(topic)}_教案.docx"
            filepath = os.path.join(task_dir, filename)
            doc.save(filepath)
            return filepath

        except Exception as e:
            print(f"创建DOCX失败: {e}")
            return None

    def _add_docx_text(self, doc, text: str):
        """添加文本到DOCX"""
        if not text:
            return

        paragraphs = text.split('\n')
        for para in paragraphs:
            para = para.strip()
            if para:
                if para.startswith('#'):
                    level = min(para.count('#'), 3)
                    clean_title = para.lstrip('#').strip()
                    doc.add_heading(clean_title, level + 1)
                else:
                    doc.add_paragraph(para)

    def _clean_filename(self, filename: str) -> str:
        """清理文件名"""
        illegal_chars = '<>:"/\\|?*'
        for char in illegal_chars:
            filename = filename.replace(char, '_')
        return filename[:80]

    def _determine_teaching_style(self, audience: str) -> dict:
        """根据受众确定教学风格"""
        styles = {
            "小学生": {"style": "游戏化教学", "depth": "基础", "language": "简单易懂，生动有趣", "interaction": "高互动，多游戏"},
            "初中生": {"style": "启发式教学", "depth": "中等", "language": "清晰准确，循序渐进", "interaction": "互动讨论，小组活动"},
            "高中生": {"style": "探究式教学", "depth": "深入", "language": "专业准确，逻辑严密", "interaction": "讨论分析，项目研究"},
            "大一新生": {"style": "引导式教学", "depth": "大学入门", "language": "专业规范，系统全面", "interaction": "小组讨论，实践项目"},
"大二学生": {"style": "自主学习引导", "depth": "专业进阶", "language": "专业深入，理论联系实际", "interaction": "研讨式学习，项目实践"},
            "研究生": {"style": "学术研究导向", "depth": "学术前沿", "language": "学术严谨，创新思维", "interaction": "学术讨论，研究项目"},
            "在职人员": {"style": "实用导向教学", "depth": "实用应用", "language": "实用易懂，直接有效", "interaction": "经验分享，案例分析"},
            "公众": {"style": "科普导向教学", "depth": "普及性", "language": "通俗易懂，生动有趣", "interaction": "互动问答，体验活动"}
        }
        return styles.get(audience, {"style": "标准教学", "depth": "中等", "language": "清晰准确", "interaction": "适当互动"})

    def _generate_lesson_plan(self, topic: str, duration: int, audience: str, subject: str, teaching_style: dict, strategy_prompt: str = "") -> str:
        """生成教案"""
        strategy_section = ""
        if strategy_prompt:
            strategy_section = f"\n{strategy_prompt}\n请在教案设计中充分体现上述教学策略智能体的建议。\n"
        
        prompt = f"""请为主题为'{topic}'、时长为{duration}分钟、面向{audience}的{subject}课程生成详细的教案。
{strategy_section}
要求：
1. 课程目标（知识目标、能力目标、情感目标）
2. 教学重点和难点
3. 教学方法（采用{teaching_style['style']}）
4. 教学过程（导入、讲解、互动、总结各环节的时间分配）
5. 评估方式
6. 参考资料

请确保内容具体、可操作，适合{audience}的认知水平。"""

        return llm_service.chat(prompt)

    def _generate_ppt_content(self, topic: str, duration: int, audience: str, lesson_plan: str,
                             template: str, subject: str, teaching_style: dict) -> str:
        """生成PPT内容"""
        prompt = f"""请根据以下教案为主题为'{topic}'、时长为{duration}分钟、面向{audience}的{subject}课程生成PPT内容。

教案：
{lesson_plan}

要求：
1. 页面标题
2. 主要内容（要点式呈现，每点不超过一行）
3. 视觉元素建议
4. 讲解要点
5. 互动建议

内容要简洁明了，重点突出，页面数量与{duration}分钟的课程时长相匹配（建议6-10页）。"""

        return llm_service.chat(prompt)

    def _generate_animation_ideas(self, topic: str, lesson_plan: str, subject: str,
                                 audience: str, teaching_style: dict, duration: int = 45) -> str:
        """生成动画创意"""
        prompt = f"""请为主题为'{topic}'、面向{audience}的{subject}课程生成动画实现方案。

教案：
{lesson_plan}

要求：
1. 动画类型选择（适合课堂教学）
2. 动画场景描述
3. 分镜脚本（每个镜头的内容和时长）
4. 制作工具推荐
5. 实现步骤

动画创意要生动有趣，帮助{audience}理解抽象概念。"""

        return llm_service.chat(prompt)

    def _generate_interactive_games(self, topic: str, audience: str, lesson_plan: str,
                                   teaching_style: dict) -> str:
        """生成互动游戏"""
        prompt = f"""请为主题为'{topic}'、面向{audience}的课程生成2-3个互动小游戏。

教案：
{lesson_plan}

每个游戏包括：
1. 游戏名称
2. 游戏类型
3. 游戏规则
4. 游戏目的
5. 所需材料
6. 游戏流程

游戏要与教学内容紧密相关，适合{audience}的年龄和认知水平。"""

        return llm_service.chat(prompt)

    def generate_outline(self, topic: str, provider: Optional[str] = None, subject: str = "general") -> str:
        """生成课件大纲"""
        if provider:
            llm_service.set_provider(provider)

        prompt = f"""请为主题为'{topic}'的{subject}课程生成一个详细的课件大纲，包括：
1. 课程目标（知识目标、能力目标、情感目标）
2. 主要内容模块（按逻辑顺序排列）
3. 教学方法
4. 评估方式
5. 教学资源推荐

请确保大纲结构清晰，内容全面。"""

        return llm_service.chat(prompt)

    def get_templates(self) -> list:
        """获取课件模板列表"""
        return [
            {"id": "standard", "name": "标准教学模板", "description": "适合一般课程"},
            {"id": "interactive", "name": "互动教学模板", "description": "强调互动和讨论"},
            {"id": "experimental", "name": "实验教学模板", "description": "适合实验课程"},
            {"id": "lecture", "name": "讲座模板", "description": "适合学术讲座"}
        ]
    
    def analyze_requirements(self, topic: str, audience: str, duration: int, 
                          key_points: list = None, reference_docs: list = None, 
                          subject: str = "general") -> dict:
        """阶段1：需求解析与课件定位 - 创建标准化课件需求说明书"""
        # 1. 分析受众画像
        audience_profile = self._analyze_audience_profile(audience)
        
        # 2. 确定课件规格
        ppt_specs = self._determine_ppt_specs(duration)
        
        # 3. 明确教学目标
        teaching_goals = self._define_teaching_goals(topic, audience, subject, key_points)
        
        # 4. 确定页面类型规范
        page_types = self._define_page_types(ppt_specs['page_count'])
        
        # 5. 整合为标准化需求说明书
        requirements = {
            "basic_info": {
                "topic": topic,
                "audience": audience,
                "duration": duration,
                "subject": subject,
                "key_points": key_points or [],
                "reference_docs": reference_docs or []
            },
            "audience_profile": audience_profile,
            "ppt_specs": ppt_specs,
            "teaching_goals": teaching_goals,
            "page_types": page_types
        }
        
        return requirements
    
    def _analyze_audience_profile(self, audience: str) -> dict:
        """分析受众画像"""
        # 受众认知水平映射
        cognitive_levels = {
            "小学生": {"level": "基础", "age_range": "6-12岁", "learning_style": "具象思维，游戏化学习"},
            "初中生": {"level": "中等", "age_range": "13-15岁", "learning_style": "逻辑思维，启发式学习"},
            "高中生": {"level": "高级", "age_range": "16-18岁", "learning_style": "抽象思维，探究式学习"},
            "大一新生": {"level": "大学入门", "age_range": "18-19岁", "learning_style": "系统学习，引导式学习"},
            "大二学生": {"level": "专业进阶", "age_range": "19-20岁", "learning_style": "自主学习，项目实践"},
            "专业学生": {"level": "专业深入", "age_range": "20-22岁", "learning_style": "研讨式学习，科研导向"},
            "研究生": {"level": "学术前沿", "age_range": "22+岁", "learning_style": "学术研究，创新思维"},
            "在职人员": {"level": "实用应用", "age_range": "25+岁", "learning_style": "实践导向，问题解决"},
            "公众": {"level": "普及性", "age_range": "广泛", "learning_style": "科普导向，趣味性"}
        }
        
        return cognitive_levels.get(audience, {
            "level": "中等",
            "age_range": "广泛",
            "learning_style": "综合学习"
        })
    
    def _determine_ppt_specs(self, duration: int) -> dict:
        """确定课件规格"""
        # 根据时长确定页数（取中间值）
        if duration <= 30:
            page_count = 8  # 6-10 的中间值
        elif duration <= 45:
            page_count = 12  # 8-15 的中间值
        else:
            page_count = 16  # 12-20 的中间值
        
        return {
            "duration": duration,
            "page_count": page_count,
            "page_range": f"{page_count-2}-{page_count+2}",
            "aspect_ratio": "16:9",
            "recommended_slide_time": round(duration / page_count, 1)
        }
    
    def _define_teaching_goals(self, topic: str, audience: str, subject: str, key_points: list) -> dict:
        """明确教学目标"""
        # 生成教学目标
        prompt = f"""请为主题为'{topic}'、面向{audience}的{subject}课程定义3-5个可落地的核心教学目标。

目标应包括：
1. 知识目标（学生应该掌握的知识）
2. 能力目标（学生应该具备的能力）
3. 情感目标（学生应该形成的态度或价值观）

如果提供了核心知识点，请围绕这些知识点展开：
{', '.join(key_points) if key_points else '无'}

请以JSON格式输出，包含knowledge_goals、ability_goals、emotional_goals三个数组。"""
        
        response = llm_service.chat(prompt)
        
        # 尝试解析JSON响应
        try:
            import json
            goals = json.loads(response)
            return goals
        except:
            # 如果解析失败，返回默认目标
            return {
                "knowledge_goals": [f"理解{topic}的基本概念"],
                "ability_goals": [f"能够应用{topic}的核心知识"],
                "emotional_goals": [f"培养对{topic}的学习兴趣"]
            }
    
    def _define_page_types(self, page_count: int) -> list:
        """确定页面类型规范"""
        # 固定支持的页面类型
        page_types = [
            {"type": "cover", "name": "封面页", "required": True, "description": "包含课程标题、副标题、授课信息"},
            {"type": "toc", "name": "目录页", "required": True, "description": "列出课程核心模块及对应页码"},
            {"type": "knowledge", "name": "知识点页", "required": True, "min_count": 3, "description": "讲解核心知识点"},
            {"type": "exercise", "name": "互动习题页", "required": True, "min_count": 1, "description": "包含互动练习题目"},
            {"type": "summary", "name": "总结页", "required": True, "description": "总结课程核心内容"},
            {"type": "extension", "name": "拓展页", "required": False, "description": "提供额外资源或延伸阅读"}
        ]
        
        # 根据总页数调整知识点页数量
        if page_count >= 12:
            page_types[2]["min_count"] = 5
        elif page_count >= 10:
            page_types[2]["min_count"] = 4
        
        return page_types
    
    def generate_ppt_outline(self, requirements: dict) -> list:
        """阶段2：结构化大纲生成 - 创建层级清晰的PPT大纲"""
        # 提取需求信息
        # 尝试多种结构获取信息
        if "basic_info" in requirements:
            basic_info = requirements["basic_info"]
            topic = basic_info.get("topic", "未命名课程")
            audience = basic_info.get("audience", "大学生")
            duration = basic_info.get("duration", 45)
            subject = basic_info.get("subject", "general")
            key_points = basic_info.get("key_points", [])
            page_types = requirements.get("page_types", [])
            teaching_goals = requirements.get("teaching_goals", {})
        else:
            # 直接从requirements中获取
            topic = requirements.get("topic", "未命名课程")
            audience = requirements.get("audience", "大学生")
            duration = requirements.get("duration", 45)
            subject = requirements.get("subject", "general")
            key_points = requirements.get("key_points", [])
            page_types = requirements.get("page_types", [])
            teaching_goals = requirements.get("teaching_goals", {})
        
        # 生成PPT大纲
        # 获取页面数量
        page_count = requirements.get("ppt_specs", {}).get("page_count", 12)
        
        # 获取教学策略注入信息
        strategy_prompt = requirements.get("strategy_prompt", "")
        strategy_section = ""
        if strategy_prompt:
            strategy_section = f"\n{strategy_prompt}\n请在大纲设计中充分体现上述教学策略建议。\n"
        
        prompt = f"""请为主题为'{topic}'、面向{audience}的{subject}课程生成一个结构化的PPT大纲。

课程信息：
- 时长：{duration}分钟
- 核心知识点：{', '.join(key_points) if key_points else '无'}
- 教学目标：
  知识目标：{', '.join(teaching_goals.get('knowledge_goals', []))}
  能力目标：{', '.join(teaching_goals.get('ability_goals', []))}
  情感目标：{', '.join(teaching_goals.get('emotional_goals', []))}
{strategy_section}
要求：
1. 大纲必须符合课堂教学逻辑：导入→知识点拆解→案例讲解→互动练习→总结→拓展
2. 单页单核心原则：每页PPT只讲1个核心知识点
3. 必备页面：必须包含封面页、目录页、≥3个知识点页、≥1个互动习题页、≥1个总结页
4. 页面数量：{page_count}页左右

请以JSON格式输出，包含以下字段：
- page_num：页码
- page_type：页面类型（cover/toc/knowledge/exercise/summary/extension）
- core_topic：核心主题（≤20字）
- content_outline：内容要点（≤5条，每条≤30字）

示例格式：
[
  {{"page_num": 1, "page_type": "cover", "core_topic": "课程封面", "content_outline": ["课程标题", "副标题", "授课信息", "日期"]}},
  {{"page_num": 2, "page_type": "toc", "core_topic": "目录", "content_outline": ["课程导入", "核心知识点1", "核心知识点2", "互动练习", "课程总结"]}},
  {{"page_num": 3, "page_type": "knowledge", "core_topic": "核心知识点1", "content_outline": ["知识点定义", "重要特征", "应用场景", "注意事项"]}},
  ...
]"""
        
        response = llm_service.chat(prompt)
        
        # 尝试解析JSON响应
        try:
            import json
            outline = json.loads(response)
            # 验证大纲格式
            return self._validate_ppt_outline(outline, requirements)
        except:
            # 如果解析失败，生成默认大纲
            return self._generate_default_outline(requirements)
    
    def _validate_ppt_outline(self, outline: list, requirements: dict) -> list:
        """验证PPT大纲格式"""
        # 检查必备页面
        required_types = ["cover", "toc", "knowledge", "exercise", "summary"]
        
        # 确保包含所有必备页面类型
        for required_type in required_types:
            # 重新提取页面类型，确保包含之前添加的页面
            page_types = [page["page_type"] for page in outline]
            if required_type not in page_types:
                # 如果缺少某类型页面，添加默认页面
                outline = self._add_missing_page(outline, required_type, requirements)
        
        # 确保至少有3个知识点页
        page_types = [page["page_type"] for page in outline]
        knowledge_count = page_types.count("knowledge")
        if knowledge_count < 3:
            for i in range(3 - knowledge_count):
                outline = self._add_missing_page(outline, "knowledge", requirements)
        
        # 重新编号页码
        for i, page in enumerate(outline, 1):
            page["page_num"] = i
        
        return outline
    
    def _add_missing_page(self, outline: list, page_type: str, requirements: dict) -> list:
        """添加缺失的页面"""
        # 尝试多种结构获取信息
        if "basic_info" in requirements:
            topic = requirements["basic_info"].get("topic", "未命名课程")
            audience = requirements["basic_info"].get("audience", "大学生")
        else:
            topic = requirements.get("topic", "未命名课程")
            audience = requirements.get("audience", "大学生")
        
        # 页面类型配置
        page_configs = {
            "cover": {
                "core_topic": "课程封面",
                "content_outline": [f"{topic}", f"面向{audience}", "课程介绍", "授课信息"]
            },
            "toc": {
                "core_topic": "目录",
                "content_outline": ["课程导入", "核心知识点", "案例分析", "互动练习", "课程总结"]
            },
            "knowledge": {
                "core_topic": f"{topic}核心知识点",
                "content_outline": ["知识点定义", "重要特征", "应用场景", "注意事项"]
            },
            "exercise": {
                "core_topic": "互动练习",
                "content_outline": ["课堂练习", "小组讨论", "问题解答", "知识巩固"]
            },
            "summary": {
                "core_topic": "课程总结",
                "content_outline": ["核心内容回顾", "学习目标达成", "课后作业", "未来展望"]
            },
            "extension": {
                "core_topic": "拓展资源",
                "content_outline": ["参考资料", "延伸阅读", "在线资源", "实践项目"]
            }
        }
        
        config = page_configs.get(page_type, page_configs["knowledge"])
        new_page = {
            "page_num": len(outline) + 1,
            "page_type": page_type,
            "core_topic": config["core_topic"],
            "content_outline": config["content_outline"]
        }
        
        # 根据页面类型插入到合适位置
        if page_type == "cover":
            outline.insert(0, new_page)
        elif page_type == "toc":
            # 尝试插入到封面页之后
            for i, page in enumerate(outline):
                if page["page_type"] != "cover":
                    outline.insert(i, new_page)
                    break
            else:
                outline.append(new_page)
        elif page_type == "summary":
            # 尝试插入到最后
            outline.append(new_page)
        elif page_type == "exercise":
            # 尝试插入到总结页之前
            for i in range(len(outline)-1, -1, -1):
                if outline[i]["page_type"] == "summary":
                    outline.insert(i, new_page)
                    break
            else:
                outline.append(new_page)
        else:  # knowledge, extension
            outline.append(new_page)
        
        return outline
    
    def _generate_default_outline(self, requirements: dict) -> list:
        """生成默认PPT大纲"""
        # 尝试多种结构获取信息
        if "basic_info" in requirements:
            topic = requirements["basic_info"].get("topic", "未命名课程")
            audience = requirements["basic_info"].get("audience", "大学生")
        else:
            topic = requirements.get("topic", "未命名课程")
            audience = requirements.get("audience", "大学生")
        
        # 获取页面数量
        page_count = requirements.get("ppt_specs", {}).get("page_count", 7)
        
        outline = [
            {"page_num": 1, "page_type": "cover", "core_topic": "课程封面", "content_outline": [f"{topic}", f"面向{audience}", "课程介绍", "授课信息"]},
            {"page_num": 2, "page_type": "toc", "core_topic": "目录", "content_outline": ["课程导入", "核心知识点1", "核心知识点2", "核心知识点3", "互动练习", "课程总结"]},
            {"page_num": 3, "page_type": "knowledge", "core_topic": "核心知识点1", "content_outline": ["知识点定义", "重要特征", "应用场景", "注意事项"]},
            {"page_num": 4, "page_type": "knowledge", "core_topic": "核心知识点2", "content_outline": ["知识点定义", "重要特征", "应用场景", "注意事项"]},
            {"page_num": 5, "page_type": "knowledge", "core_topic": "核心知识点3", "content_outline": ["知识点定义", "重要特征", "应用场景", "注意事项"]},
            {"page_num": 6, "page_type": "exercise", "core_topic": "互动练习", "content_outline": ["课堂练习", "小组讨论", "问题解答", "知识巩固"]},
            {"page_num": 7, "page_type": "summary", "core_topic": "课程总结", "content_outline": ["核心内容回顾", "学习目标达成", "课后作业", "未来展望"]}
        ]
        
        # 根据需求调整大纲
        if page_count > 7:
            # 添加拓展页
            outline.append({
                "page_num": 8, "page_type": "extension", "core_topic": "拓展资源", 
                "content_outline": ["参考资料", "延伸阅读", "在线资源", "实践项目"]
            })
        
        return outline
    
    def generate_detailed_content(self, outline: list, requirements: dict) -> list:
        """阶段3：分页面精细化内容生成 - 为每页PPT生成详细内容"""
        detailed_pages = []
        
        for page in outline:
            # 根据页面类型生成详细内容
            if page["page_type"] == "cover":
                detailed_content = self._generate_cover_content(page, requirements)
            elif page["page_type"] == "toc":
                detailed_content = self._generate_toc_content(page, outline)
            elif page["page_type"] == "knowledge":
                detailed_content = self._generate_knowledge_content(page, requirements)
            elif page["page_type"] == "exercise":
                detailed_content = self._generate_exercise_content(page, requirements)
            elif page["page_type"] == "summary":
                detailed_content = self._generate_summary_content(page, requirements)
            elif page["page_type"] == "extension":
                detailed_content = self._generate_extension_content(page, requirements)
            else:
                detailed_content = self._generate_default_content(page, requirements)
            
            detailed_pages.append(detailed_content)
        
        return detailed_pages
    
    def _generate_cover_content(self, page: dict, requirements: dict) -> dict:
        """生成封面页详细内容"""
        # 尝试多种结构获取信息
        if "basic_info" in requirements:
            topic = requirements["basic_info"].get("topic", "未命名课程")
            audience = requirements["basic_info"].get("audience", "大学生")
            duration = requirements["basic_info"].get("duration", 45)
            subject = requirements["basic_info"].get("subject", "general")
        else:
            topic = requirements.get("topic", "未命名课程")
            audience = requirements.get("audience", "大学生")
            duration = requirements.get("duration", 45)
            subject = requirements.get("subject", "general")
        
        # 生成封面页内容
        prompt = f"""请为主题为'{topic}'、面向{audience}的{subject}课程生成封面页的详细内容。

要求：
1. 主标题：简洁明了，突出课程主题（≤20字）
2. 副标题：补充说明课程内容或目标（≤30字）
3. 授课人信息：教师姓名/机构（可选）
4. 视觉元素提示：适合课程主题的图片或图标建议

请以JSON格式输出，包含以下字段：
- page_num：页码
- page_type：页面类型
- core_topic：核心主题
- main_title：主标题
- subtitle：副标题
- instructor_info：授课人信息
- visual_elelements：视觉元素提示
- notes：讲师备注"""
        
        response = llm_service.chat(prompt)
        
        try:
            import json
            content = json.loads(response)
            # 合并基本信息
            content.update({
                "page_num": page["page_num"],
                "page_type": page["page_type"],
                "core_topic": page["core_topic"],
                "media_type": "image",
                "media_desc": content.get("visual_elelements", "适合课程主题的封面图")
            })
            return content
        except:
            # 默认内容
            return {
                "page_num": page["page_num"],
                "page_type": page["page_type"],
                "core_topic": page["core_topic"],
                "main_title": topic,
                "subtitle": f"面向{audience}的{subject}课程",
                "instructor_info": "授课教师",
                "visual_elelements": f"{topic}相关的专业图片",
                "notes": "欢迎学生，介绍课程目标",
                "media_type": "image",
                "media_desc": f"{topic}相关的封面图"
            }
    
    def _generate_toc_content(self, page: dict, outline: list) -> dict:
        """生成目录页详细内容"""
        # 提取目录项
        toc_items = []
        for i, item in enumerate(outline[1:], 1):  # 跳过封面页
            toc_items.append(f"{i}. {item['core_topic']}")
        
        return {
            "page_num": page["page_num"],
            "page_type": page["page_type"],
            "core_topic": page["core_topic"],
            "toc_items": toc_items,
            "notes": "概述课程结构，引导学生了解学习内容",
            "media_type": "none",
            "media_desc": "无"
        }
    
    def _generate_knowledge_content(self, page: dict, requirements: dict) -> dict:
        """生成知识点页详细内容"""
        # 尝试多种结构获取信息
        if "basic_info" in requirements:
            topic = requirements["basic_info"].get("topic", "未命名课程")
            audience = requirements["basic_info"].get("audience", "大学生")
            subject = requirements["basic_info"].get("subject", "general")
        else:
            topic = requirements.get("topic", "未命名课程")
            audience = requirements.get("audience", "大学生")
            subject = requirements.get("subject", "general")
        core_topic = page["core_topic"]
        
        # 检索该知识点的知识库上下文
        page_knowledge = ""
        try:
            from .rag_service import rag_service
            page_knowledge = rag_service.get_context_for_generation(core_topic, audience)
        except Exception:
            pass
        
        # 合并知识库上下文和参考资料
        extra_context = ""
        if page_knowledge:
            extra_context += f"\n相关知识库参考:\n{page_knowledge}\n"
        ref_content = requirements.get("reference_content", "")
        if ref_content:
            extra_context += f"\n上传的参考资料摘要:\n{ref_content[:800]}\n"
        if extra_context:
            extra_context += "请参考以上资料来丰富内容。\n"
        
        # 生成知识点内容
        prompt = f"""请为主题为'{topic}'、面向{audience}的{subject}课程的知识点页生成详细内容。

当前知识点：{core_topic}
{extra_context}
要求：
1. 核心知识点标题：清晰准确（≤20字）
2. 拆解要点：3-5个要点，每条≤30字，逻辑清晰
3. 配套案例：1个具象化案例，帮助理解
4. 视觉元素提示：适合该知识点的图片或图表建议
5. 讲解要点：教师授课时的注意事项

请以JSON格式输出，包含以下字段：
- page_num：页码
- page_type：页面类型
- core_topic：核心主题
- key_points：拆解要点（数组）
- case_study：配套案例
- visual_elelements：视觉元素提示
- teaching_notes：讲解要点
- media_type：推荐的媒体类型（image/table/formula）"""
        
        response = llm_service.chat(prompt)
        
        try:
            import json
            content = json.loads(response)
            # 合并基本信息
            content.update({
                "page_num": page["page_num"],
                "page_type": page["page_type"],
                "core_topic": page["core_topic"]
            })
            return content
        except:
            # 默认内容
            return {
                "page_num": page["page_num"],
                "page_type": page["page_type"],
                "core_topic": page["core_topic"],
                "key_points": [
                    "知识点基本定义",
                    "重要特征和属性",
                    "实际应用场景",
                    "常见错误和注意事项"
                ],
                "case_study": f"关于{core_topic}的实际应用案例",
                "visual_elelements": f"{core_topic}相关的示意图",
                "teaching_notes": "重点讲解核心概念，确保学生理解",
                "media_type": "image",
                "media_desc": f"{core_topic}相关的示意图"
            }
    
    def _generate_exercise_content(self, page: dict, requirements: dict) -> dict:
        """生成互动习题页详细内容"""
        # 尝试多种结构获取信息
        if "basic_info" in requirements:
            topic = requirements["basic_info"].get("topic", "未命名课程")
            audience = requirements["basic_info"].get("audience", "大学生")
            subject = requirements["basic_info"].get("subject", "general")
        else:
            topic = requirements.get("topic", "未命名课程")
            audience = requirements.get("audience", "大学生")
            subject = requirements.get("subject", "general")
        
        # 生成习题内容
        prompt = f"""请为主题为'{topic}'、面向{audience}的{subject}课程生成互动习题页的详细内容。

要求：
1. 1-2道互动题（单选/多选/简答）
2. 题目描述：清晰明确
3. 选项（如果是选择题）：4个选项
4. 正确答案：明确指出
5. 知识点解析：详细说明考察的知识点
6. 互动建议：如何组织课堂互动

请以JSON格式输出，包含以下字段：
- page_num：页码
- page_type：页面类型
- core_topic：核心主题
- exercises：习题列表（包含题目、选项、答案、解析）
- interaction_suggestions：互动建议
- notes：讲师备注"""
        
        response = llm_service.chat(prompt)
        
        try:
            import json
            content = json.loads(response)
            # 合并基本信息
            content.update({
                "page_num": page["page_num"],
                "page_type": page["page_type"],
                "core_topic": page["core_topic"],
                "media_type": "none",
                "media_desc": "无"
            })
            return content
        except:
            # 默认内容
            return {
                "page_num": page["page_num"],
                "page_type": page["page_type"],
                "core_topic": page["core_topic"],
                "exercises": [
                    {
                        "question": f"关于{topic}的核心概念，以下说法正确的是？",
                        "type": "multiple_choice",
                        "options": [
                            "选项A",
                            "选项B",
                            "选项C",
                            "选项D"
                        ],
                        "answer": "选项A",
                        "explanation": "详细解析为什么选项A正确"
                    }
                ],
                "interaction_suggestions": "组织小组讨论，鼓励学生分享思考过程",
                "notes": "通过习题巩固所学知识，及时反馈",
                "media_type": "none",
                "media_desc": "无"
            }
    
    def _generate_summary_content(self, page: dict, requirements: dict) -> dict:
        """生成总结页详细内容"""
        # 尝试多种结构获取信息
        if "basic_info" in requirements:
            topic = requirements["basic_info"].get("topic", "未命名课程")
            audience = requirements["basic_info"].get("audience", "大学生")
        else:
            topic = requirements.get("topic", "未命名课程")
            audience = requirements.get("audience", "大学生")
        teaching_goals = requirements.get("teaching_goals", {})
        
        # 生成总结内容
        prompt = f"""请为主题为'{topic}'、面向{audience}的课程生成总结页的详细内容。

教学目标：
- 知识目标：{', '.join(teaching_goals.get('knowledge_goals', []))}
- 能力目标：{', '.join(teaching_goals.get('ability_goals', []))}
- 情感目标：{', '.join(teaching_goals.get('emotional_goals', []))}

要求：
1. 核心知识点复盘：总结课程的核心内容
2. 学习目标完成情况：评估教学目标的达成情况
3. 课后思考方向：提供学生课后思考的问题
4. 课后作业：布置相关作业

请以JSON格式输出，包含以下字段：
- page_num：页码
- page_type：页面类型
- core_topic：核心主题
- knowledge_review：核心知识点复盘
- goals_achievement：学习目标完成情况
- after_class_thoughts：课后思考方向
- homework：课后作业
- notes：讲师备注"""
        
        response = llm_service.chat(prompt)
        
        try:
            import json
            content = json.loads(response)
            # 合并基本信息
            content.update({
                "page_num": page["page_num"],
                "page_type": page["page_type"],
                "core_topic": page["core_topic"],
                "media_type": "none",
                "media_desc": "无"
            })
            return content
        except:
            # 默认内容
            return {
                "page_num": page["page_num"],
                "page_type": page["page_type"],
                "core_topic": page["core_topic"],
                "knowledge_review": f"总结{topic}的核心知识点",
                "goals_achievement": "完成了课程的主要教学目标",
                "after_class_thoughts": [
                    f"如何将{topic}应用到实际场景？",
                    f"{topic}与其他知识的联系是什么？"
                ],
                "homework": f"完成与{topic}相关的练习",
                "notes": "总结课程内容，强调重点，布置作业",
                "media_type": "none",
                "media_desc": "无"
            }
    
    def _generate_extension_content(self, page: dict, requirements: dict) -> dict:
        """生成拓展页详细内容"""
        # 尝试多种结构获取信息
        if "basic_info" in requirements:
            topic = requirements["basic_info"].get("topic", "未命名课程")
            subject = requirements["basic_info"].get("subject", "general")
        else:
            topic = requirements.get("topic", "未命名课程")
            subject = requirements.get("subject", "general")
        
        # 生成拓展内容
        prompt = f"""请为主题为'{topic}'、学科为{subject}的课程生成拓展页的详细内容。

要求：
1. 参考资料：推荐相关书籍、论文或文章
2. 延伸阅读：提供深入学习的方向
3. 在线资源：推荐相关网站或视频
4. 实践项目：建议学生可以尝试的实践活动

请以JSON格式输出，包含以下字段：
- page_num：页码
- page_type：页面类型
- core_topic：核心主题
- reference_materials：参考资料
- further_reading：延伸阅读
- online_resources：在线资源
- practice_projects：实践项目
- notes：讲师备注"""
        
        response = llm_service.chat(prompt)
        
        try:
            import json
            content = json.loads(response)
            # 合并基本信息
            content.update({
                "page_num": page["page_num"],
                "page_type": page["page_type"],
                "core_topic": page["core_topic"],
                "media_type": "none",
                "media_desc": "无"
            })
            return content
        except:
            # 默认内容
            return {
                "page_num": page["page_num"],
                "page_type": page["page_type"],
                "core_topic": page["core_topic"],
                "reference_materials": ["推荐相关书籍1", "推荐相关书籍2"],
                "further_reading": ["深入学习方向1", "深入学习方向2"],
                "online_resources": ["相关网站1", "相关视频资源"],
                "practice_projects": [f"{topic}相关实践项目1", f"{topic}相关实践项目2"],
                "notes": "提供额外学习资源，鼓励学生深入学习",
                "media_type": "none",
                "media_desc": "无"
            }
    
    def _generate_default_content(self, page: dict, requirements: dict) -> dict:
        """生成默认页面内容"""
        return {
            "page_num": page["page_num"],
            "page_type": page["page_type"],
            "core_topic": page["core_topic"],
            "key_points": ["内容要点1", "内容要点2", "内容要点3"],
            "notes": "页面内容",
            "media_type": "none",
            "media_desc": "无"
        }
    
    def generate_visual_style(self, topic: str, subject: str, audience: str) -> dict:
        """阶段4：PPT视觉与格式规范生成 - 创建配套的PPT样式规范"""
        # 生成视觉样式规范
        prompt = f"""请为主题为'{topic}'、学科为{subject}、面向{audience}的课程生成PPT视觉与格式规范。

要求：
1. 全局统一视觉规范：
   - 主色调：适合课程主题的颜色方案
   - 辅助色：搭配主色调的辅助颜色
   - 字体规范：标题和正文的字号、字体、行间距
   - 页面边距：统一的页面边距设置

2. 分页面布局规范：
   - 封面页：元素位置和尺寸
   - 目录页：目录项的布局
   - 知识点页：标题、内容、图片的布局
   - 习题页：题目和选项的布局
   - 总结页：总结内容的布局

3. 中文适配要求：
   - 默认使用微软雅黑/思源黑体等中文友好字体
   - 正文字号≥18号，标题字号≥28号
   - 确保投影场景清晰可见

4. 风格统一：
   - 全PPT风格统一，视觉效果专业
   - 符合教学场景的视觉要求

请以JSON格式输出，包含以下字段：
- global_styles：全局样式规范
- page_layouts：分页面布局规范
- font_specs：字体规范
- color_scheme：颜色方案"""
        
        response = llm_service.chat(prompt)
        
        try:
            import json
            style = json.loads(response)
            # 验证并补充样式规范
            return self._validate_visual_style(style)
        except:
            # 如果解析失败，生成默认样式规范
            return self._generate_default_visual_style()
    
    def _validate_visual_style(self, style: dict) -> dict:
        """验证视觉样式规范"""
        # 确保所有必要字段存在
        default_style = self._generate_default_visual_style()
        
        # 合并并补充缺失的字段
        for key in default_style:
            if key not in style:
                style[key] = default_style[key]
            else:
                # 补充子字段
                for sub_key in default_style[key]:
                    if sub_key not in style[key]:
                        style[key][sub_key] = default_style[key][sub_key]
        
        return style
    
    def _generate_default_visual_style(self) -> dict:
        """生成默认视觉样式规范"""
        return {
            "global_styles": {
                "aspect_ratio": "16:9",
                "slide_width": 13.333,  # 英寸
                "slide_height": 7.5,     # 英寸
                "margin_left": 0.8,      # 英寸
                "margin_top": 0.8,       # 英寸
                "margin_right": 0.8,     # 英寸
                "margin_bottom": 0.8      # 英寸
            },
            "page_layouts": {
                "cover": {
                    "title_position": {"x": 0.8, "y": 2.5, "width": 11, "height": 1.5},
                    "subtitle_position": {"x": 0.8, "y": 4.2, "width": 11, "height": 1},
                    "instructor_position": {"x": 0.8, "y": 5.5, "width": 11, "height": 0.5}
                },
                "toc": {
                    "title_position": {"x": 0.8, "y": 0.5, "width": 11, "height": 1},
                    "content_position": {"x": 2, "y": 2.0, "width": 9, "height": 4.5}
                },
                "knowledge": {
                    "title_position": {"x": 0.5, "y": 0.4, "width": 12, "height": 1},
                    "content_position": {"x": 0.8, "y": 1.5, "width": 11.5, "height": 5.5}
                },
                "exercise": {
                    "title_position": {"x": 0.5, "y": 0.4, "width": 12, "height": 1},
                    "content_position": {"x": 0.8, "y": 1.5, "width": 11.5, "height": 5.5}
                },
                "summary": {
                    "title_position": {"x": 0.5, "y": 0.5, "width": 12, "height": 1},
                    "content_position": {"x": 1.5, "y": 1.5, "width": 10, "height": 5}
                },
                "extension": {
                    "title_position": {"x": 0.5, "y": 0.4, "width": 12, "height": 1},
                    "content_position": {"x": 0.8, "y": 1.5, "width": 11.5, "height": 5.5}
                }
            },
            "font_specs": {
                "title": {
                    "font": "微软雅黑",
                    "size": 36,
                    "bold": True,
                    "color": "#2C3E50"
                },
                "subtitle": {
                    "font": "微软雅黑",
                    "size": 24,
                    "bold": False,
                    "color": "#34495E"
                },
                "content": {
                    "font": "微软雅黑",
                    "size": 20,
                    "bold": False,
                    "color": "#34495E"
                },
                "small_content": {
                    "font": "微软雅黑",
                    "size": 18,
                    "bold": False,
                    "color": "#7F8C8D"
                }
            },
            "color_scheme": {
                "primary": "#3498DB",  # 主色调
                "secondary": "#2ECC71",  # 辅助色
                "accent1": "#E74C3C",  # 强调色1
                "accent2": "#F39C12",  # 强调色2
                "background": "#FFFFFF",  # 背景色
                "text": "#2C3E50"  # 文本色
            }
        }
    
    def apply_style_to_ppt(self, prs, style: dict):
        """应用视觉样式到PPT"""
        # 设置幻灯片尺寸
        from pptx.util import Inches
        prs.slide_width = Inches(style["global_styles"]["slide_width"])
        prs.slide_height = Inches(style["global_styles"]["slide_height"])
        
        # 应用颜色方案
        # 注意：python-pptx的颜色方案设置较为复杂，这里只做基础设置
        
        return prs
