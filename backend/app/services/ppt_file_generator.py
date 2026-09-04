"""PPT文件生成服务 - 把结构化JSON数据转换成精美的.pptx文件"""
import os
import json
from datetime import datetime
from typing import Optional, Dict, List

# 设计思路参考：清华大学THU-MAIC/OpenMAIC开源项目，核心代码自主实现

# 尝试导入python-pptx库
try:
    from pptx import Presentation
    from pptx.util import Inches, Pt, Emu
    from pptx.dml.color import RGBColor as RgbColor
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.enum.shapes import MSO_SHAPE
    PPTX_AVAILABLE = True
except ImportError:
    PPTX_AVAILABLE = False

# 尝试导入图片服务
try:
    from .image_service import image_service
    IMAGE_SERVICE_AVAILABLE = True
except ImportError:
    IMAGE_SERVICE_AVAILABLE = False

# 尝试导入LaTeX渲染服务
try:
    from .latex_renderer import has_latex, strip_latex
    LATEX_AVAILABLE = True
except ImportError:
    LATEX_AVAILABLE = False


class PPTFileGenerator:
    """PPT文件生成器类 - 生成排版精美、可直接授课使用的PPT课件"""

    # 幻灯片尺寸（16:9 宽屏）
    SLIDE_WIDTH = Inches(13.333)
    SLIDE_HEIGHT = Inches(7.5)

    # 字体名称
    FONT_TITLE = "微软雅黑"
    FONT_BODY = "微软雅黑"

    def __init__(self, output_dir: str = "generated_courseware"):
        """初始化PPT文件生成器"""
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        # 主题色配置：primary(主色)、secondary(深色)、accent(辅助亮色)、light(浅色背景)、text(正文色)
        self.theme_colors = {
            "蓝色系": {
                "primary": (41, 128, 185),
                "secondary": (31, 97, 141),
                "accent": (52, 152, 219),
                "light": (214, 234, 248),
                "text": (44, 62, 80),
                "white": (255, 255, 255),
            },
            "绿色系": {
                "primary": (39, 174, 96),
                "secondary": (30, 132, 73),
                "accent": (46, 204, 113),
                "light": (212, 239, 223),
                "text": (44, 62, 80),
                "white": (255, 255, 255),
            },
            "红色系": {
                "primary": (192, 57, 43),
                "secondary": (148, 49, 38),
                "accent": (231, 76, 60),
                "light": (245, 215, 210),
                "text": (44, 62, 80),
                "white": (255, 255, 255),
            },
            "紫色系": {
                "primary": (142, 68, 173),
                "secondary": (108, 52, 131),
                "accent": (155, 89, 182),
                "light": (232, 218, 239),
                "text": (44, 62, 80),
                "white": (255, 255, 255),
            },
            "橙色系": {
                "primary": (211, 84, 0),
                "secondary": (175, 70, 0),
                "accent": (243, 156, 18),
                "light": (253, 235, 208),
                "text": (44, 62, 80),
                "white": (255, 255, 255),
            },
        }

    def _rgb(self, color_tuple):
        """元组转RgbColor"""
        return RgbColor(*color_tuple)

    def _get_colors(self, theme_color: str) -> Dict:
        """获取主题色配置"""
        return self.theme_colors.get(theme_color, self.theme_colors["蓝色系"])

    # ============ 公共布局组件 ============

    def _add_top_bar(self, slide, prs, colors, height=Inches(0.06)):
        """添加顶部主色细条"""
        shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, height)
        shape.fill.solid()
        shape.fill.fore_color.rgb = self._rgb(colors["primary"])
        shape.line.fill.background()

    def _add_left_sidebar(self, slide, prs, colors, width=Inches(0.45)):
        """添加左侧竖色条装饰"""
        shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, width, prs.slide_height)
        shape.fill.solid()
        shape.fill.fore_color.rgb = self._rgb(colors["primary"])
        shape.line.fill.background()

    def _add_page_number(self, slide, prs, page_num: int, total_pages: int, colors):
        """添加页码"""
        box = slide.shapes.add_textbox(Inches(11.5), Inches(6.9), Inches(1.5), Inches(0.4))
        tf = box.text_frame
        p = tf.paragraphs[0]
        p.text = f"{page_num} / {total_pages}"
        p.font.size = Pt(11)
        p.font.color.rgb = RgbColor(160, 160, 160)
        p.alignment = PP_ALIGN.RIGHT

    def _add_bottom_line(self, slide, prs, colors):
        """添加底部细线"""
        shape = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(7.0), Inches(11.7), Inches(0.02)
        )
        shape.fill.solid()
        shape.fill.fore_color.rgb = RgbColor(220, 220, 220)
        shape.line.fill.background()

    def _add_section_title(self, slide, title_text: str, colors, left=Inches(0.8), top=Inches(0.35), width=Inches(11), font_size=Pt(32)):
        """添加章节标题（带小色块装饰）"""
        # 小色块
        marker = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top + Inches(0.08), Inches(0.18), Inches(0.45))
        marker.fill.solid()
        marker.fill.fore_color.rgb = self._rgb(colors["primary"])
        marker.line.fill.background()

        # 标题文字
        box = slide.shapes.add_textbox(left + Inches(0.35), top, width, Inches(0.7))
        tf = box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = title_text
        p.font.size = font_size
        p.font.bold = True
        p.font.color.rgb = self._rgb(colors["text"])
        p.font.name = self.FONT_TITLE

    def _add_subtitle_text(self, slide, text: str, colors, left=Inches(1.15), top=Inches(1.1), width=Inches(10.5), font_size=Pt(16)):
        """添加小节标题/描述"""
        box = slide.shapes.add_textbox(left, top, width, Inches(0.5))
        tf = box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = text
        p.font.size = font_size
        p.font.bold = True
        p.font.color.rgb = self._rgb(colors["primary"])
        p.font.name = self.FONT_BODY

    def _add_bullet_points(self, slide, points: list, colors, left=Inches(1.15), top=Inches(1.6), width=Inches(10.5), max_height=Inches(4.5), font_size=Pt(18)):
        """添加要点列表：使用单一文本框多段落排版，避免多文本框高度不足导致的叠字/重影。"""
        if not points:
            return

        cleaned = []
        for point in points:
            if not point:
                continue
            pt = str(point).strip()
            if not pt:
                continue
            # 幻灯片内不插入公式图片，避免与文字叠层；公式改为纯文本说明
            if LATEX_AVAILABLE and has_latex(pt):
                pt = strip_latex(pt)
            cleaned.append(pt)

        if not cleaned:
            return

        box = slide.shapes.add_textbox(left, top, width, max_height)
        tf = box.text_frame
        tf.word_wrap = True
        tf.margin_left = Pt(6)
        tf.margin_right = Pt(6)
        tf.margin_top = Pt(4)
        tf.margin_bottom = Pt(4)

        for i, point_text in enumerate(cleaned):
            if i == 0:
                p = tf.paragraphs[0]
            else:
                p = tf.add_paragraph()
            p.text = f"\u2022  {point_text}"
            p.font.size = font_size
            p.font.color.rgb = self._rgb(colors["text"])
            p.font.name = self.FONT_BODY
            p.space_after = Pt(10)
            p.line_spacing = 1.25

    # ============ 各类页面生成 ============

    def generate_pptx(self, ppt_content: Dict, task_dir: str = None) -> Optional[str]:
        """生成PPTX文件"""
        if not PPTX_AVAILABLE:
            print("Error: python-pptx library is not installed")
            return None

        try:
            metadata = ppt_content.get("metadata", {})
            topic = metadata.get("topic", "未命名课程")
            theme_color = metadata.get("theme_color", "蓝色系")
            subject = metadata.get("subject", "general")
            detailed_content = ppt_content.get("detailed_content", [])

            if not task_dir:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                task_dir = os.path.join(self.output_dir, f"{self._clean_filename(topic)}_{timestamp}")
            os.makedirs(task_dir, exist_ok=True)

            # AI自动获取/生成配图
            slide_images = {}
            if IMAGE_SERVICE_AVAILABLE:
                try:
                    slide_images = image_service.get_images_for_slides(
                        detailed_content, theme_color=theme_color, subject=subject
                    )
                    print(f"已为 {len(slide_images)} 页幻灯片准备配图")
                except Exception as e:
                    print(f"获取幻灯片配图失败(不影响生成): {e}")

            prs = Presentation()
            prs.slide_width = self.SLIDE_WIDTH
            prs.slide_height = self.SLIDE_HEIGHT

            colors = self._get_colors(theme_color)
            total_pages = len(detailed_content) + 1  # +1 是感谢页

            for page_content in detailed_content:
                page_type = page_content.get("page_type")
                page_num = page_content.get("page_num", 0)
                if page_type == "cover":
                    self._add_cover_slide(prs, page_content, colors, metadata)
                elif page_type == "toc":
                    self._add_toc_slide(prs, page_content, colors, page_num, total_pages)
                elif page_type == "knowledge":
                    img_path = slide_images.get(page_num)
                    self._add_knowledge_slide(prs, page_content, colors, page_num, total_pages, image_path=img_path)
                elif page_type == "exercise":
                    self._add_exercise_slide(prs, page_content, colors, page_num, total_pages)
                elif page_type == "summary":
                    self._add_summary_slide(prs, page_content, colors, page_num, total_pages)
                elif page_type == "extension":
                    self._add_extension_slide(prs, page_content, colors, page_num, total_pages)
                else:
                    self._add_default_slide(prs, page_content, colors, page_num, total_pages)

            # 添加感谢页
            self._add_thank_you_slide(prs, colors, topic)

            # 保存文件
            filename = f"{self._clean_filename(topic)}_课件.pptx"
            filepath = os.path.join(task_dir, filename)
            prs.save(filepath)

            # 保存生成数据
            data_path = os.path.join(task_dir, "ppt_data.json")
            with open(data_path, "w", encoding="utf-8") as f:
                json.dump(ppt_content, f, ensure_ascii=False, indent=2)

            return filepath

        except Exception as e:
            print(f"创建PPTX失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    # ---------- 封面页 ----------
    def _add_cover_slide(self, prs, page_content: dict, colors: dict, metadata: dict):
        """添加精美封面页"""
        slide = prs.slides.add_slide(prs.slide_layouts[6])  # 空白布局

        # 背景：主色全覆盖
        bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
        bg.fill.solid()
        bg.fill.fore_color.rgb = self._rgb(colors["primary"])
        bg.line.fill.background()

        # 右上装饰圆
        d1 = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(9.2), Inches(-1.5), Inches(5.5), Inches(5.5))
        d1.fill.solid()
        d1.fill.fore_color.rgb = self._rgb(colors["secondary"])
        d1.line.fill.background()

        # 左下装饰圆
        d2 = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(-2), Inches(4.5), Inches(5), Inches(5))
        d2.fill.solid()
        d2.fill.fore_color.rgb = self._rgb(colors["secondary"])
        d2.line.fill.background()

        # 白色半透明横条，承载文字
        bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(2.2), prs.slide_width, Inches(3.5))
        bar.fill.solid()
        bar.fill.fore_color.rgb = self._rgb(colors["secondary"])
        bar.line.fill.background()

        # 主标题
        main_title = page_content.get("main_title", page_content.get("core_topic", metadata.get("topic", "课程")))
        title_box = slide.shapes.add_textbox(Inches(1), Inches(2.5), Inches(11.3), Inches(1.3))
        tf = title_box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = main_title
        p.font.size = Pt(48)
        p.font.bold = True
        p.font.color.rgb = RgbColor(255, 255, 255)
        p.font.name = self.FONT_TITLE
        p.alignment = PP_ALIGN.CENTER

        # 副标题
        subtitle = page_content.get("subtitle", "")
        if not subtitle:
            audience = metadata.get("audience", "")
            duration = metadata.get("duration", "")
            subject = metadata.get("subject", "")
            parts = []
            if audience:
                parts.append(f"面向{audience}")
            if subject and subject != "general":
                parts.append(f"{subject}课程")
            if duration:
                parts.append(f"{duration}分钟")
            subtitle = "  |  ".join(parts) if parts else ""
        if subtitle:
            sub_box = slide.shapes.add_textbox(Inches(1), Inches(3.9), Inches(11.3), Inches(0.7))
            tf = sub_box.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = subtitle
            p.font.size = Pt(22)
            p.font.color.rgb = RgbColor(230, 230, 230)
            p.font.name = self.FONT_BODY
            p.alignment = PP_ALIGN.CENTER

        # 授课人 + 日期
        instructor = page_content.get("instructor_info", "授课教师")
        info_box = slide.shapes.add_textbox(Inches(1), Inches(4.8), Inches(11.3), Inches(0.5))
        tf = info_box.text_frame
        p = tf.paragraphs[0]
        p.text = f"{instructor}    {datetime.now().strftime('%Y年%m月%d日')}"
        p.font.size = Pt(16)
        p.font.color.rgb = RgbColor(200, 200, 200)
        p.font.name = self.FONT_BODY
        p.alignment = PP_ALIGN.CENTER

        # 底部装饰窄条
        bottom = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(7.15), prs.slide_width, Inches(0.35))
        bottom.fill.solid()
        bottom.fill.fore_color.rgb = self._rgb(colors["accent"])
        bottom.line.fill.background()

    # ---------- 目录页 ----------
    def _add_toc_slide(self, prs, page_content: dict, colors: dict, page_num: int, total: int):
        """添加目录页"""
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        self._add_top_bar(slide, prs, colors)
        self._add_section_title(slide, page_content.get("core_topic", "课程目录"), colors, font_size=Pt(36))

        toc_items = page_content.get("toc_items", [])

        # 用卡片式布局展示目录项
        start_y = Inches(1.5)
        col_width = Inches(5.5)
        item_height = Inches(0.8)

        for i, item in enumerate(toc_items):
            if not item:
                continue
            col = 0 if i % 2 == 0 else 1
            row = i // 2
            x = Inches(1.2) + col * (col_width + Inches(0.5))
            y = start_y + row * item_height

            if y > Inches(6.5):
                break

            # 序号圆形
            circle = slide.shapes.add_shape(MSO_SHAPE.OVAL, x, y + Inches(0.05), Inches(0.5), Inches(0.5))
            circle.fill.solid()
            circle.fill.fore_color.rgb = self._rgb(colors["primary"])
            circle.line.fill.background()
            # 序号文字
            ctf = circle.text_frame
            ctf.paragraphs[0].text = str(i + 1)
            ctf.paragraphs[0].font.size = Pt(16)
            ctf.paragraphs[0].font.bold = True
            ctf.paragraphs[0].font.color.rgb = RgbColor(255, 255, 255)
            ctf.paragraphs[0].alignment = PP_ALIGN.CENTER
            ctf.paragraphs[0].font.name = self.FONT_BODY
            ctf.word_wrap = False

            # 目录项文字
            tbox = slide.shapes.add_textbox(x + Inches(0.65), y + Inches(0.05), col_width - Inches(0.8), Inches(0.5))
            tf = tbox.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = str(item)
            p.font.size = Pt(18)
            p.font.color.rgb = self._rgb(colors["text"])
            p.font.name = self.FONT_BODY

        self._add_bottom_line(slide, prs, colors)
        self._add_page_number(slide, prs, page_num, total, colors)

    # ---------- 知识点页 ----------
    def _add_knowledge_slide(self, prs, page_content: dict, colors: dict, page_num: int, total: int, image_path: str = None):
        """添加知识点页 - 单页单知识点，左侧色条+标题+要点+配图+案例"""
        slide = prs.slides.add_slide(prs.slide_layouts[6])

        # 左侧色条
        self._add_left_sidebar(slide, prs, colors, width=Inches(0.35))
        self._add_top_bar(slide, prs, colors, height=Inches(0.05))

        core_topic = page_content.get("core_topic", "知识点")

        # 页面标题
        self._add_section_title(slide, core_topic, colors, left=Inches(0.7), top=Inches(0.3), font_size=Pt(30))

        # 分隔线
        sep = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.7), Inches(1.05), Inches(11.5), Inches(0.02))
        sep.fill.solid()
        sep.fill.fore_color.rgb = self._rgb(colors["light"])
        sep.line.fill.background()

        # 判断是否有配图 - 有图时调整布局
        has_image = image_path and os.path.exists(image_path)

        # 核心要点 (有图时缩窄宽度, 给图片留出空间)
        key_points = page_content.get("key_points", [])
        if key_points:
            if has_image:
                self._add_bullet_points(slide, key_points, colors, left=Inches(0.9), top=Inches(1.3), width=Inches(6.8), max_height=Inches(3.2), font_size=Pt(18))
            else:
                self._add_bullet_points(slide, key_points, colors, left=Inches(0.9), top=Inches(1.3), width=Inches(11.3), max_height=Inches(3.2), font_size=Pt(18))

        # 插入配图
        if has_image:
            try:
                # 图片区域: 右侧, 与要点并排
                img_left = Inches(8.1)
                img_top = Inches(1.2)
                img_width = Inches(4.5)
                img_height = Inches(3.3)

                # 图片边框背景
                img_bg = slide.shapes.add_shape(
                    MSO_SHAPE.ROUNDED_RECTANGLE,
                    img_left - Inches(0.08), img_top - Inches(0.08),
                    img_width + Inches(0.16), img_height + Inches(0.16)
                )
                img_bg.fill.solid()
                img_bg.fill.fore_color.rgb = self._rgb(colors["light"])
                img_bg.line.fill.background()

                # 插入图片
                slide.shapes.add_picture(
                    image_path, img_left, img_top, img_width, img_height
                )
            except Exception as e:
                print(f"插入图片失败(第{page_num}页): {e}")

        # 案例分析区域
        case_study = page_content.get("case_study", "")
        if case_study:
            case_y = Inches(4.7)
            # 案例背景色块
            case_bg = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.7), case_y, Inches(11.8), Inches(1.8))
            case_bg.fill.solid()
            case_bg.fill.fore_color.rgb = self._rgb(colors["light"])
            case_bg.line.fill.background()

            # 案例标签
            label_box = slide.shapes.add_textbox(Inches(1.0), case_y + Inches(0.15), Inches(2), Inches(0.4))
            tf = label_box.text_frame
            p = tf.paragraphs[0]
            p.text = "\U0001F4A1 案例分析"
            p.font.size = Pt(15)
            p.font.bold = True
            p.font.color.rgb = self._rgb(colors["primary"])
            p.font.name = self.FONT_BODY

            # 案例内容
            case_box = slide.shapes.add_textbox(Inches(1.0), case_y + Inches(0.5), Inches(11.2), Inches(1.2))
            tf = case_box.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = str(case_study)[:300]  # 限制长度
            p.font.size = Pt(14)
            p.font.color.rgb = self._rgb(colors["text"])
            p.font.name = self.FONT_BODY
            p.line_spacing = Pt(22)

        self._add_bottom_line(slide, prs, colors)
        self._add_page_number(slide, prs, page_num, total, colors)

    # ---------- 互动练习页 ----------
    def _add_exercise_slide(self, prs, page_content: dict, colors: dict, page_num: int, total: int):
        """添加互动练习页"""
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        self._add_left_sidebar(slide, prs, colors, width=Inches(0.35))
        self._add_top_bar(slide, prs, colors, height=Inches(0.05))

        core_topic = page_content.get("core_topic", "课堂互动练习")
        self._add_section_title(slide, core_topic, colors, left=Inches(0.7), top=Inches(0.3), font_size=Pt(30))

        sep = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.7), Inches(1.05), Inches(11.5), Inches(0.02))
        sep.fill.solid()
        sep.fill.fore_color.rgb = self._rgb(colors["light"])
        sep.line.fill.background()

        exercises = page_content.get("exercises", [])
        y = Inches(1.3)

        for i, ex in enumerate(exercises[:3]):  # 最多显示3道题
            if not isinstance(ex, dict):
                continue
            question = ex.get("question", "")
            if not question:
                continue

            # 题号+题目
            q_box = slide.shapes.add_textbox(Inches(0.9), y, Inches(11.3), Inches(0.5))
            tf = q_box.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = f"第{i+1}题：{question}"
            p.font.size = Pt(17)
            p.font.bold = True
            p.font.color.rgb = self._rgb(colors["text"])
            p.font.name = self.FONT_BODY
            y += Inches(0.55)

            # 选项
            options = ex.get("options", [])
            if options:
                for opt in options[:4]:
                    opt_box = slide.shapes.add_textbox(Inches(1.5), y, Inches(10), Inches(0.35))
                    tf = opt_box.text_frame
                    tf.word_wrap = True
                    p = tf.paragraphs[0]
                    p.text = str(opt)
                    p.font.size = Pt(15)
                    p.font.color.rgb = self._rgb(colors["text"])
                    p.font.name = self.FONT_BODY
                    y += Inches(0.35)

            # 答案
            answer = ex.get("answer", "")
            if answer:
                ans_box = slide.shapes.add_textbox(Inches(1.2), y, Inches(10), Inches(0.35))
                tf = ans_box.text_frame
                p = tf.paragraphs[0]
                p.text = f"\u2714 答案：{answer}"
                p.font.size = Pt(14)
                p.font.bold = True
                p.font.color.rgb = self._rgb(colors["primary"])
                p.font.name = self.FONT_BODY
                y += Inches(0.45)

            y += Inches(0.15)
            if y > Inches(6.5):
                break

        self._add_bottom_line(slide, prs, colors)
        self._add_page_number(slide, prs, page_num, total, colors)

    # ---------- 总结页 ----------
    def _add_summary_slide(self, prs, page_content: dict, colors: dict, page_num: int, total: int):
        """添加课程总结页"""
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        self._add_left_sidebar(slide, prs, colors, width=Inches(0.35))
        self._add_top_bar(slide, prs, colors, height=Inches(0.05))

        core_topic = page_content.get("core_topic", "课程总结")
        self._add_section_title(slide, core_topic, colors, left=Inches(0.7), top=Inches(0.3), font_size=Pt(30))

        sep = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.7), Inches(1.05), Inches(11.5), Inches(0.02))
        sep.fill.solid()
        sep.fill.fore_color.rgb = self._rgb(colors["light"])
        sep.line.fill.background()

        # 知识点复盘
        knowledge_review = page_content.get("knowledge_review", [])
        if not isinstance(knowledge_review, list):
            knowledge_review = [knowledge_review]

        y = Inches(1.3)
        if knowledge_review:
            # 复盘标题
            self._add_subtitle_text(slide, "\u2705 核心知识点复盘", colors, left=Inches(0.9), top=y, font_size=Pt(18))
            y += Inches(0.5)

            for item in knowledge_review[:6]:
                if not item:
                    continue
                box = slide.shapes.add_textbox(Inches(1.3), y, Inches(10.5), Inches(0.45))
                tf = box.text_frame
                tf.word_wrap = True
                p = tf.paragraphs[0]
                p.text = f"\u2713  {item}"
                p.font.size = Pt(16)
                p.font.color.rgb = self._rgb(colors["text"])
                p.font.name = self.FONT_BODY
                y += Inches(0.45)

        # 学习目标完成
        goals = page_content.get("goals_achievement", "")
        if goals:
            y += Inches(0.2)
            self._add_subtitle_text(slide, "\U0001F3AF 学习目标达成", colors, left=Inches(0.9), top=y, font_size=Pt(18))
            y += Inches(0.45)
            gbox = slide.shapes.add_textbox(Inches(1.3), y, Inches(10.5), Inches(0.6))
            tf = gbox.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = str(goals)
            p.font.size = Pt(15)
            p.font.color.rgb = self._rgb(colors["text"])
            p.font.name = self.FONT_BODY
            y += Inches(0.6)

        # 课后作业
        homework = page_content.get("homework", "")
        if homework:
            y += Inches(0.1)
            # 作业背景色块
            hw_bg = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.7), y, Inches(11.8), Inches(1.5))
            hw_bg.fill.solid()
            hw_bg.fill.fore_color.rgb = self._rgb(colors["light"])
            hw_bg.line.fill.background()

            self._add_subtitle_text(slide, "\U0001F4DD 课后作业", colors, left=Inches(1.0), top=y + Inches(0.1), font_size=Pt(16))
            hw_box = slide.shapes.add_textbox(Inches(1.0), y + Inches(0.45), Inches(11.2), Inches(0.95))
            tf = hw_box.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = str(homework)[:300]
            p.font.size = Pt(14)
            p.font.color.rgb = self._rgb(colors["text"])
            p.font.name = self.FONT_BODY
            p.line_spacing = Pt(22)

        self._add_bottom_line(slide, prs, colors)
        self._add_page_number(slide, prs, page_num, total, colors)

    # ---------- 拓展页 ----------
    def _add_extension_slide(self, prs, page_content: dict, colors: dict, page_num: int, total: int):
        """添加拓展资源页"""
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        self._add_left_sidebar(slide, prs, colors, width=Inches(0.35))
        self._add_top_bar(slide, prs, colors, height=Inches(0.05))

        core_topic = page_content.get("core_topic", "拓展资源")
        self._add_section_title(slide, core_topic, colors, left=Inches(0.7), top=Inches(0.3), font_size=Pt(30))

        sep = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.7), Inches(1.05), Inches(11.5), Inches(0.02))
        sep.fill.solid()
        sep.fill.fore_color.rgb = self._rgb(colors["light"])
        sep.line.fill.background()

        y = Inches(1.3)

        # 课后思考
        thoughts = page_content.get("after_class_thoughts", [])
        if thoughts:
            if not isinstance(thoughts, list):
                thoughts = [thoughts]
            self._add_subtitle_text(slide, "\U0001F914 课后思考", colors, left=Inches(0.9), top=y, font_size=Pt(18))
            y += Inches(0.45)
            for t in thoughts[:3]:
                box = slide.shapes.add_textbox(Inches(1.3), y, Inches(10.5), Inches(0.4))
                tf = box.text_frame
                tf.word_wrap = True
                p = tf.paragraphs[0]
                p.text = f"\u2022  {t}"
                p.font.size = Pt(15)
                p.font.color.rgb = self._rgb(colors["text"])
                p.font.name = self.FONT_BODY
                y += Inches(0.4)

        # 参考资料
        refs = page_content.get("reference_materials", [])
        if refs:
            if not isinstance(refs, list):
                refs = [refs]
            y += Inches(0.2)
            self._add_subtitle_text(slide, "\U0001F4DA 推荐资源", colors, left=Inches(0.9), top=y, font_size=Pt(18))
            y += Inches(0.45)
            for r in refs[:4]:
                box = slide.shapes.add_textbox(Inches(1.3), y, Inches(10.5), Inches(0.4))
                tf = box.text_frame
                tf.word_wrap = True
                p = tf.paragraphs[0]
                p.text = f"\u2022  {r}"
                p.font.size = Pt(15)
                p.font.color.rgb = self._rgb(colors["text"])
                p.font.name = self.FONT_BODY
                y += Inches(0.4)

        # 实践项目
        projects = page_content.get("practice_projects", [])
        if projects:
            if not isinstance(projects, list):
                projects = [projects]
            y += Inches(0.2)
            self._add_subtitle_text(slide, "\U0001F6E0 实践项目", colors, left=Inches(0.9), top=y, font_size=Pt(18))
            y += Inches(0.45)
            for proj in projects[:3]:
                box = slide.shapes.add_textbox(Inches(1.3), y, Inches(10.5), Inches(0.4))
                tf = box.text_frame
                tf.word_wrap = True
                p = tf.paragraphs[0]
                p.text = f"\u2022  {proj}"
                p.font.size = Pt(15)
                p.font.color.rgb = self._rgb(colors["text"])
                p.font.name = self.FONT_BODY
                y += Inches(0.4)

        self._add_bottom_line(slide, prs, colors)
        self._add_page_number(slide, prs, page_num, total, colors)

    # ---------- 默认页 ----------
    def _add_default_slide(self, prs, page_content: dict, colors: dict, page_num: int, total: int):
        """添加默认页面"""
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        self._add_left_sidebar(slide, prs, colors, width=Inches(0.35))
        self._add_top_bar(slide, prs, colors, height=Inches(0.05))

        core_topic = page_content.get("core_topic", "内容")
        self._add_section_title(slide, core_topic, colors, left=Inches(0.7), top=Inches(0.3), font_size=Pt(30))

        key_points = page_content.get("key_points", page_content.get("content_outline", []))
        if key_points:
            self._add_bullet_points(slide, key_points, colors, left=Inches(0.9), top=Inches(1.3), width=Inches(11.3))

        self._add_bottom_line(slide, prs, colors)
        self._add_page_number(slide, prs, page_num, total, colors)

    # ---------- 感谢页 ----------
    def _add_thank_you_slide(self, prs, colors: dict, topic: str):
        """添加感谢页"""
        slide = prs.slides.add_slide(prs.slide_layouts[6])

        # 背景：主色
        bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
        bg.fill.solid()
        bg.fill.fore_color.rgb = self._rgb(colors["primary"])
        bg.line.fill.background()

        # 装饰圆
        d1 = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(9.5), Inches(-2), Inches(5), Inches(5))
        d1.fill.solid()
        d1.fill.fore_color.rgb = self._rgb(colors["secondary"])
        d1.line.fill.background()

        d2 = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(-2.5), Inches(5), Inches(4.5), Inches(4.5))
        d2.fill.solid()
        d2.fill.fore_color.rgb = self._rgb(colors["secondary"])
        d2.line.fill.background()

        # 感谢文字
        title_box = slide.shapes.add_textbox(Inches(1), Inches(2.5), Inches(11.3), Inches(1.5))
        tf = title_box.text_frame
        p = tf.paragraphs[0]
        p.text = "感谢聆听"
        p.font.size = Pt(64)
        p.font.bold = True
        p.font.color.rgb = RgbColor(255, 255, 255)
        p.font.name = self.FONT_TITLE
        p.alignment = PP_ALIGN.CENTER

        # 副标题
        sub_box = slide.shapes.add_textbox(Inches(1), Inches(4.2), Inches(11.3), Inches(0.7))
        tf = sub_box.text_frame
        p = tf.paragraphs[0]
        p.text = "THANKS FOR LISTENING"
        p.font.size = Pt(20)
        p.font.color.rgb = RgbColor(200, 200, 200)
        p.font.name = self.FONT_BODY
        p.alignment = PP_ALIGN.CENTER

        # 答疑提示
        qa_box = slide.shapes.add_textbox(Inches(1), Inches(5.2), Inches(11.3), Inches(0.5))
        tf = qa_box.text_frame
        p = tf.paragraphs[0]
        p.text = "欢迎提问与交流  |  联系方式：_____________"
        p.font.size = Pt(16)
        p.font.color.rgb = RgbColor(180, 180, 180)
        p.font.name = self.FONT_BODY
        p.alignment = PP_ALIGN.CENTER

        # 底部装饰
        bottom = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(7.15), prs.slide_width, Inches(0.35))
        bottom.fill.solid()
        bottom.fill.fore_color.rgb = self._rgb(colors["accent"])
        bottom.line.fill.background()

    # ============ 工具方法 ============

    def _clean_filename(self, filename: str) -> str:
        """清理文件名"""
        illegal_chars = '<>:"/\\|?*'
        for char in illegal_chars:
            filename = filename.replace(char, "_")
        return filename[:80]
