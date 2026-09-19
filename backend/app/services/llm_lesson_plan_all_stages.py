# 全学段教案生成核心逻辑
# 包含通义千问API调用、全阶段教案生成、分学段/分大学专业适配、双重合规校验

import json
import time
import re
import os
from typing import Dict, List, Optional, Any
from .prompts.lesson_plan_prompts import LessonPlanPrompts
from .university_major_config import UniversityMajorConfig
from .llm_service import llm_service
from .topic_expansion import enrich_for_lesson_plan

try:
    from .rag_service import rag_service as _rag_service
except Exception:  # pragma: no cover - RAG 可选
    _rag_service = None

class LessonPlanGenerator:
    """全学段教案生成器"""

    # ---- 排版尺度：集中一处，避免同一份文档里 11pt / 12pt 混着用 ----
    # 中文文档的常规层级：标题三号(16) / 小标题四号(14) / 正文小四(12) / 表格五号(10.5)
    _SZ_H1 = 22      # 文档主标题（课题）
    _SZ_H2 = 16      # 章节标题（一、二、三）
    _SZ_H3 = 14      # 小节标题
    _SZ_BODY = 12    # 正文
    _SZ_TABLE = 10.5  # 表格内文字

    def __init__(self):
        """初始化教案生成器"""
        self.prompts = LessonPlanPrompts()
        self.university_config = UniversityMajorConfig()

    # ------------------------------------------------------------------
    # 内容形状 → 可读文本
    # ------------------------------------------------------------------
    # 为什么单独做这一层：模型返回的字段形状不固定，而渲染代码里到处是 str(v)。
    # `str({'具体目标': '能说出…'})` 会把 Python 的 repr 原样写进 Word —— 线上
    # 真的出现过：教学目标表格的单元格里躺着 `{'具体目标': "能准确说出…`。
    # 一个 dict 该怎么读，必须由渲染层决定，不能拿语言内部的 repr 当文档内容。
    # ------------------------------------------------------------------

    @staticmethod
    def _plain_scalar(value) -> str:
        """标量 → 文本。空值给空串，布尔给人话，整数不做 float 化。"""
        if value is None:
            return ""
        if isinstance(value, bool):
            return "是" if value else "否"
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        if isinstance(value, (int, float, str)):
            return str(value).strip()
        return ""

    # 「- xxx」「1. xxx」「• xxx」这类行首标记，判断字面量前要先剥掉
    _LIST_MARKER = re.compile(r"^\s*(?:[-*•◦▪]|\d+[.、])\s*")

    @classmethod
    def _heal_literals(cls, value, depth: int = 0):
        """把"长得像 Python 字面量"的字符串还原成结构。

        为什么需要：模型有时把一条作业写成**字符串**
        `"{'题目': '…', '评分标准': '…'}"` —— 提示词里给的是 Python 风格示例，
        它就把 repr 照抄了。这串东西一路传到渲染层，`str()` 之后原样印进 Word，
        用户看到的是「1. {'题目': '体积为200 cm³…'}」（线上真的这样产出过）。

        判定得了就还原，判定不了**原样保留** —— 渲染层不负责猜内容，
        但"这串文本是不是一个结构"是能判定的。绝不为了好看丢掉内容。
        """
        if depth > 6:
            return value
        if isinstance(value, dict):
            return {k: cls._heal_literals(v, depth + 1) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._heal_literals(v, depth + 1) for v in value]
        if not isinstance(value, str):
            return value

        body = cls._LIST_MARKER.sub("", value).strip()
        if len(body) < 4 or len(body) > 20000:
            return value
        if not ((body.startswith("{") and body.endswith("}"))
                or (body.startswith("[") and body.endswith("]"))):
            return value
        try:
            import ast
            parsed = ast.literal_eval(body)
        except (ValueError, SyntaxError, MemoryError, RecursionError):
            return value
        if isinstance(parsed, (dict, list)):
            return cls._heal_literals(parsed, depth + 1)
        return value

    @classmethod
    def _flatten(cls, value, level: int = 0):
        """任意形状 → [(层级, 文本)]。

        dict → 「键：值」，值还是复合结构就下沉一层；
        list → 逐项摊平（**不**输出方括号与引号）；
        标量 → 原样。
        """
        rows = []
        if isinstance(value, dict):
            for key, sub in value.items():
                name = cls._plain_scalar(key) or str(key).strip()
                if isinstance(sub, (dict, list, tuple)):
                    kids = cls._flatten(sub, level + 1)
                    if len(kids) == 1 and kids[0][0] == level + 1:
                        rows.append((level, f"{name}：{kids[0][1]}"))
                    elif kids:
                        rows.append((level, f"{name}："))
                        rows.extend(kids)
                    else:
                        rows.append((level, name))
                else:
                    text = cls._plain_scalar(sub)
                    rows.append((level, f"{name}：{text}" if text else name))
        elif isinstance(value, (list, tuple)):
            for sub in value:
                rows.extend(cls._flatten(sub, level))
        else:
            text = cls._plain_scalar(value)
            if text:
                rows.append((level, text))
        return rows

    @classmethod
    def _plain_block(cls, value, max_rows: int = 60) -> str:
        """摊成多行文本（写进表格单元格）。

        层级用缩进 + 项目符号表达 —— **不用** `- ` 这种伪列表：
        那在 Word 里就是个普通破折号，既没有悬挂缩进也不会随样式变，
        多行缩进只能靠空格硬凑（原实现里真的出现过 "-    单位：…"）。
        """
        rows = cls._flatten(value)[:max_rows]
        if not rows:
            return ""
        lines = []
        for lv, text in rows:
            lines.append(text if lv == 0 else f"{'    ' * (lv - 1)}• {text}")
        return "\n".join(lines)

    @classmethod
    def _numbered_block(cls, value, max_rows: int = 60) -> str:
        """像 _plain_block，但顶层条目带序号（教学目标这类"几条"的内容）"""
        rows = cls._flatten(value)[:max_rows]
        if not rows:
            return ""
        lines, n = [], 0
        for lv, text in rows:
            if lv == 0:
                n += 1
                lines.append(f"{n}. {text}")
            else:
                lines.append(f"{'    ' * (lv - 1)}• {text}")
        return "\n".join(lines)
    
    def analyze_requirements(self, level: str, subject: str, grade: str, topic: str, 
                           duration: int, requirements: str = "") -> Dict[str, Any]:
        """阶段1：全学段需求解析与合规校验"""
        try:
            # 1. 分析学段适配规则
            level_rules = self._get_level_rules(level)
            
            # 2. 分析学科/专业适配规则
            subject_rules = self._get_subject_rules(level, subject)
            
            # 3. 确定核心教学目标
            core_goals = self._define_core_goals(topic, level, subject)
            
            # 4. 确定知识点范围
            knowledge_scope = self._define_knowledge_scope(topic, level, subject)
            
            # 5. 合规校验
            compliance_result = self._validate_compliance(level, subject, topic)
            
            # 5.5 用户仅填主题或补充过少时，自动扩写具体教学线索
            req_enriched = requirements
            if not (requirements and len(str(requirements).strip()) >= 50):
                try:
                    req_enriched = enrich_for_lesson_plan(level, subject, topic, duration, requirements or "")
                except Exception:
                    req_enriched = requirements

            # 6. 构建需求执行清单
            requirements_list = {
                "basic_info": {
                    "level": level,
                    "subject": subject,
                    "grade": grade,
                    "topic": topic,
                    "duration": duration,
                    "requirements": req_enriched
                },
                "level_rules": level_rules,
                "subject_rules": subject_rules,
                "core_goals": core_goals,
                "knowledge_scope": knowledge_scope,
                "compliance_result": compliance_result
            }
            
            return requirements_list
            
        except Exception as e:
            raise Exception(f"需求解析失败: {str(e)}")
    
    def generate_outline(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """阶段2：教案结构化大纲生成"""
        try:
            level = requirements["basic_info"]["level"]
            subject = requirements["basic_info"]["subject"]
            topic = requirements["basic_info"]["topic"]
            duration = requirements["basic_info"]["duration"]
            
            # 1. 确定模块结构
            modules = self._define_modules(level, subject)
            
            # 2. 划分教学环节
            sections = self._define_sections(level, duration)
            
            # 3. 分配时长
            time_allocation = self._allocate_time(sections, duration)
            
            # 4. 确定核心知识点
            core_knowledge = requirements.get("knowledge_scope", [])
            
            # 5. 确定对应课程目标（大学专用）
            course_goals = []
            if level == "普通高等院校":
                course_goals = self._define_course_goals(topic, subject)
            
            # 6. 构建大纲
            outline = {
                "modules": modules,
                "sections": sections,
                "time_allocation": time_allocation,
                "core_knowledge": core_knowledge,
                "course_goals": course_goals
            }
            
            return outline
            
        except Exception as e:
            raise Exception(f"大纲生成失败: {str(e)}")
    
    def generate_detailed_content(self, outline: Dict[str, Any], requirements: Dict[str, Any]) -> Dict[str, Any]:
        """阶段3：分模块精细化内容生成"""
        try:
            level = requirements["basic_info"]["level"]
            subject = requirements["basic_info"]["subject"]
            topic = requirements["basic_info"]["topic"]
            duration = requirements["basic_info"]["duration"]
            grade = requirements["basic_info"]["grade"]
            
            # 1. 根据学段和专业选择合适的Prompt模板
            prompt_template = self._select_prompt_template(level, subject)
            
            # 2. 构建Prompt参数
            prompt_params = {
                "level": level,
                "subject": subject,
                "grade": grade,
                "topic": topic,
                "duration": duration,
                "requirements": requirements["basic_info"].get("requirements", "")
            }
            
            # 2.5 检索知识库上下文并注入prompt
            knowledge_ctx = ""
            if _rag_service:
                try:
                    knowledge_ctx = _rag_service.get_context_for_generation(topic, f"{level} {subject}")
                except Exception:
                    pass
            
            # 3. 生成教案内容（学段差异化说明 + 学科提示）
            prompt = prompt_template.format(**prompt_params)
            prompt += self.prompts.get_level_subject_addon(level, subject)
            if knowledge_ctx:
                prompt += f"\n\n{knowledge_ctx}\n请参考以上知识库资料来丰富教案内容。"
            response = llm_service.chat(prompt)
            
            # 4. 解析生成的内容
            lesson_plan = self._parse_lesson_plan(response)
            
            # 5. 确保内容完整性
            lesson_plan = self._ensure_content_completeness(lesson_plan, level, subject)
            
            return lesson_plan
            
        except Exception as e:
            raise Exception(f"精细化内容生成失败: {str(e)}")
    
    def validate_compliance(self, lesson_plan: Dict[str, Any], level: str, subject: str) -> Dict[str, Any]:
        """阶段4：教学合规性与学段/专业适配性双重校验"""
        try:
            # 1. 规范合规性校验
            compliance_issues = self._validate_norm_compliance(lesson_plan, level, subject)
            
            # 2. 内容专业性校验
            content_issues = self._validate_content_professionalism(lesson_plan, level, subject)
            
            # 3. 生成校验报告
            all_issues = compliance_issues + content_issues
            compliance_result = "通过" if len(all_issues) == 0 else "不通过"
            
            # 4. 生成修正方案
            correction_plan = self._generate_correction_plan(all_issues)
            
            # 5. 生成优化建议
            optimization_suggestions = self._generate_optimization_suggestions(lesson_plan, level, subject)
            
            # 6. 构建校验报告
            validation_report = {
                "compliance_result": compliance_result,
                "issue_list": all_issues,
                "correction_plan": correction_plan,
                "optimization_suggestions": optimization_suggestions
            }
            
            # 7. 如果校验不通过，自动修正
            if compliance_result == "不通过":
                lesson_plan = self._auto_correct_lesson_plan(lesson_plan, correction_plan)
            
            return {
                "validation_report": validation_report,
                "corrected_lesson_plan": lesson_plan
            }
            
        except Exception as e:
            raise Exception(f"合规性校验失败: {str(e)}")
    
    def modify_lesson_plan(self, existing_lesson_plan: Dict[str, Any], level: str, 
                         subject: str, grade: str, modification_requirements: str) -> Dict[str, Any]:
        """阶段5：迭代修改与版本管理"""
        try:
            # 1. 构建迭代修改Prompt
            prompt = self.prompts.ITERATIVE_MODIFICATION_TEMPLATE.format(
                level=level,
                subject=subject,
                grade=grade,
                existing_lesson_plan=json.dumps(existing_lesson_plan, ensure_ascii=False),
                modification_requirements=modification_requirements
            )
            
            # 2. 调用LLM进行修改
            response = llm_service.chat(prompt)
            
            # 3. 解析修改结果
            modification_result = self._parse_modification_result(response)
            
            # 4. 生成新版本号
            modification_result["version"] = self._generate_version_number()
            
            return modification_result
            
        except Exception as e:
            raise Exception(f"教案修改失败: {str(e)}")
    
    def export_lesson_plan(self, lesson_plan: Dict[str, Any], export_format: str = "json",
                           output_dir: str = "generated_lesson_plans", topic: str = None) -> Any:
        """阶段6：多格式导出与跨模块内容同步
        
        对于json格式返回JSON字符串
        对于docx格式返回生成的文件路径
        """
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            if export_format == "json":
                return json.dumps(lesson_plan, ensure_ascii=False, indent=2)
            elif export_format == "docx":
                return self._export_to_docx(lesson_plan, output_dir, topic)
            elif export_format == "pdf":
                # PDF暂时生成docx
                return self._export_to_docx(lesson_plan, output_dir, topic)
            else:
                raise Exception(f"不支持的导出格式: {export_format}")
                
        except Exception as e:
            raise Exception(f"教案导出失败: {str(e)}")
    
    def _export_to_docx(self, lesson_plan: Dict[str, Any], output_dir: str, topic: str = None) -> str:
        """生成专业的Word教案文档，返回文件路径"""
        from docx import Document
        from docx.shared import Inches, Pt, Cm, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.enum.table import WD_TABLE_ALIGNMENT
        from docx.oxml.ns import qn
        
        doc = Document()
        
        # ========== 纸张与边距（A4，中文公文规范）==========
        # python-docx 的默认模板是 **Letter（21.6×27.9cm）**，不是 A4。
        # 不显式设置的话，教案在打印机上会按 Letter 排版：右边距对不上、
        # 最后一列被裁掉。中文教案一律 A4（21×29.7cm）。
        for section in doc.sections:
            section.page_width = Cm(21)
            section.page_height = Cm(29.7)
            section.top_margin = Cm(2.5)
            section.bottom_margin = Cm(2.5)
            section.left_margin = Cm(3)
            section.right_margin = Cm(3)
        
        # ========== 设置默认字体 ==========
        style = doc.styles['Normal']
        font = style.font
        font.name = 'Times New Roman'
        font.size = Pt(self._SZ_BODY)
        style.element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
        style.paragraph_format.line_spacing = 1.5
        
        # ========== 提取基本信息 ==========
        # 先自愈：模型偶尔把结构写成字符串（repr），不还原就会原样印进文档
        lesson_plan = self._heal_literals(lesson_plan)
        basic_info = lesson_plan.get("教案基本信息", {})
        # 优先使用传入的topic参数，确保文件名与用户输入一致
        if not topic:
            topic = basic_info.get("课题", basic_info.get("教学主题", "教案"))
        
        # ========== 标题 ==========
        title_para = doc.add_paragraph()
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_run = title_para.add_run(f"{topic}")
        title_run.bold = True
        title_run.font.size = Pt(self._SZ_H1)
        title_run.font.color.rgb = RGBColor(0x1A, 0x5C, 0xA8)
        self._set_cn_font(title_run, '黑体')
        
        subtitle_para = doc.add_paragraph()
        subtitle_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        subtitle_run = subtitle_para.add_run("教 案")
        subtitle_run.bold = True
        subtitle_run.font.size = Pt(self._SZ_H2)
        subtitle_run.font.color.rgb = RGBColor(0x33, 0x33, 0x33)
        self._set_cn_font(subtitle_run, '黑体')
        
        # ========== 基本信息表格 ==========
        doc.add_paragraph()
        self._add_section_heading(doc, "一、教案基本信息")
        
        info_map = [
            ("课程名称", ["课题", "教学主题", "课程名称"]),
            ("授课教师", ["授课教师", "教师"]),
            ("授课班级", ["授课班级", "班级"]),
            ("课    时", ["授课时长", "课时", "课时数"]),
            ("学科/专业", ["学科", "专业", "学科/专业"]),
            ("年级/课型", ["年级", "课型", "年级/课型"]),
            ("教材版本", ["教材版本", "对应教材章节", "教材"]),
            ("课标依据", ["课标依据", "课标出处", "课程标准依据"]),
            ("授课日期", ["授课日期", "日期"]),
            ("学    段", ["学段"]),
            ("教学地点", ["教学地点", "地点"]),
        ]
        info_rows = []
        for label, keys in info_map:
            val = ""
            for key in keys:
                val = basic_info.get(key, "")
                if val:
                    break
                for alt_key in basic_info.keys():
                    if key in alt_key:
                        val = basic_info.get(alt_key, "")
                        if val:
                            break
                if val:
                    break
            # str(val) 在这里是错的：模型有时把"教材版本"给成 {"版本":…,"章节":…}，
            # str() 会把 repr 印进表格（这一处和教学目标那处是同一个病）
            text = val if isinstance(val, str) else self._plain_block(val)
            info_rows.append((label, text.strip() if text and text.strip() else "________"))
        
        cols = 4
        table = doc.add_table(rows=0, cols=cols)
        table.style = 'Table Grid'
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        for i in range(0, len(info_rows), 2):
            row = table.add_row()
            self._set_cell(row.cells[0], info_rows[i][0], bold=True, bg_color="E8EEF7")
            self._set_cell(row.cells[1], info_rows[i][1])
            if i + 1 < len(info_rows):
                self._set_cell(row.cells[2], info_rows[i+1][0], bold=True, bg_color="E8EEF7")
                self._set_cell(row.cells[3], info_rows[i+1][1])
        self._fix_layout(table)
        
        # ========== 教学目标 ==========
        # 说明：这里**不再硬编码"三维目标"**。
        # 2022 年版义务教育课程方案与课程标准已明确"从三维目标转向课程核心素养"，
        # 各学科按本学科核心素养维度表述（如语文：文化自信/语言运用/思维能力/审美创造）。
        # 因此渲染器做成"维度无关"：模型返回什么维度就渲染什么维度，
        # 既支持核心素养，也兼容历史遗留的三维目标输出，不会把无法识别的维度
        # 悄悄塞进"知识与技能"里（那会静默篡改教案内容）。
        goals = lesson_plan.get("教学目标", [])
        self._add_section_heading(doc, "二、教学目标")

        goal_categories = self._group_goals(goals)

        goal_table = doc.add_table(rows=len(goal_categories) + 1, cols=2)
        goal_table.style = 'Table Grid'
        goal_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        self._set_header_cell(goal_table.rows[0].cells[0], "目标维度")
        self._set_header_cell(goal_table.rows[0].cells[1], "具体目标")

        for idx, (cat_name, cat_items) in enumerate(goal_categories):
            row = goal_table.rows[idx + 1]
            self._set_cell(row.cells[0], cat_name, bold=True, bg_color="E8EEF7", width=Cm(3.5))
            # 逐条编号：cat_items 已是纯文本（_group_goals 里展平过），这里只负责排版
            content_text = "\n".join(
                f"{i}. {item}" for i, item in enumerate(cat_items, 1)
            ) if cat_items else "（请根据实际情况补充）"
            self._set_cell(row.cells[1], content_text)
        self._repeat_header(goal_table.rows[0])
        self._fix_layout(goal_table)
        
        # ========== 教学重难点（表格）==========
        focus = lesson_plan.get("教学重难点", {})
        self._add_section_heading(doc, "三、教学重难点")
        
        focus_data = {"教学重点": "", "教学难点": "", "突破策略": ""}
        if isinstance(focus, dict):
            # 统一走 _plain_block：list 逐条一行、dict 变「键：值」，
            # 不再出现 "- xxx" 伪列表与 str(list) 的字面量
            for fkey in ["教学重点", "重点"]:
                if fkey in focus:
                    focus_data["教学重点"] = self._plain_block(focus[fkey])
                    break
            for fkey in ["教学难点", "难点"]:
                if fkey in focus:
                    focus_data["教学难点"] = self._plain_block(focus[fkey])
                    break
            for fkey in ["突破策略", "重难点突破", "突破方法", "解决策略"]:
                if fkey in focus:
                    focus_data["突破策略"] = self._plain_block(focus[fkey])
                    break
            # 收集未匹配的内容
            known_focus = {"教学重点", "重点", "教学难点", "难点", "突破策略", "重难点突破", "突破方法", "解决策略"}
            for k, v in focus.items():
                if k not in known_focus and not focus_data["突破策略"]:
                    inner = self._plain_block(v)
                    focus_data["突破策略"] = f"{k}：\n{inner}" if inner else str(k)
        elif isinstance(focus, str):
            focus_data["教学重点"] = focus
        
        focus_table = doc.add_table(rows=3, cols=2)
        focus_table.style = 'Table Grid'
        focus_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        for idx, (fk, fv) in enumerate(focus_data.items()):
            self._set_cell(focus_table.rows[idx].cells[0], fk, bold=True, bg_color="E8EEF7", width=Cm(3.5))
            self._set_cell(focus_table.rows[idx].cells[1], fv if fv else "（请根据实际情况补充）")
        self._fix_layout(focus_table)
        
        # ========== 教学准备（表格）==========
        preparation = lesson_plan.get("教学准备", {})
        self._add_section_heading(doc, "四、教学准备")
        
        prep_data = {"教师准备": "", "学生准备": "", "教学媒体": ""}
        if isinstance(preparation, dict):
            teacher_keys = ["教师准备", "教具准备", "教师", "教具"]
            student_keys = ["学生准备", "课前预习", "学生", "预习"]
            media_keys = ["教学媒体", "多媒体", "课件", "教学工具", "媒体"]
            for tk in teacher_keys:
                if tk in preparation:
                    prep_data["教师准备"] = self._plain_block(preparation[tk])
                    break
            for sk in student_keys:
                if sk in preparation:
                    prep_data["学生准备"] = self._plain_block(preparation[sk])
                    break
            for mk in media_keys:
                if mk in preparation:
                    prep_data["教学媒体"] = self._plain_block(preparation[mk])
                    break
            # 未匹配的内容归入教师准备
            matched_prep = set(teacher_keys + student_keys + media_keys)
            extra_items = []
            for k, v in preparation.items():
                if k not in matched_prep:
                    inner = self._plain_block(v)
                    extra_items.append(f"{k}：{inner}" if inner else str(k))
            if extra_items:
                merged = "\n".join(extra_items)
                prep_data["教师准备"] = (
                    f"{prep_data['教师准备']}\n{merged}" if prep_data["教师准备"] else merged
                )
        elif isinstance(preparation, list):
            prep_data["教师准备"] = self._plain_block(preparation)
        elif isinstance(preparation, str):
            prep_data["教师准备"] = preparation
        
        prep_table = doc.add_table(rows=3, cols=2)
        prep_table.style = 'Table Grid'
        prep_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        for idx, (pk, pv) in enumerate(prep_data.items()):
            self._set_cell(prep_table.rows[idx].cells[0], pk, bold=True, bg_color="E8EEF7", width=Cm(3.5))
            self._set_cell(prep_table.rows[idx].cells[1], pv if pv else "（请根据实际情况补充）")
        self._fix_layout(prep_table)
        
        # ========== 教学过程设计（统一大表格）==========
        process = lesson_plan.get("教学过程设计", [])
        self._add_section_heading(doc, "五、教学过程设计")
        
        process_headers = ["教学环节", "时间分配", "教师活动", "学生活动", "设计意图"]
        process_col_widths = [Cm(2.5), Cm(2), Cm(5), Cm(4.5), Cm(3.5)]
        
        if isinstance(process, list) and process:
            num_rows = 1 + len(process)
            process_table = doc.add_table(rows=num_rows, cols=5)
            process_table.style = 'Table Grid'
            process_table.alignment = WD_TABLE_ALIGNMENT.CENTER
            
            # 表头行
            for ci, header in enumerate(process_headers):
                self._set_header_cell(process_table.rows[0].cells[ci], header, width=process_col_widths[ci])
            
            # 数据行
            for ri, step in enumerate(process):
                row = process_table.rows[ri + 1]
                if isinstance(step, dict):
                    step_name = step.get("环节", step.get("教学环节", step.get("name", f"环节{ri+1}")))
                    step_time = step.get("时长", step.get("duration", step.get("时间", "")))
                    teacher_act = step.get("教师活动", "")
                    student_act = step.get("学生活动", "")
                    design_intent = step.get("设计意图", "")
                    
                    # 将教学内容、PPT页码等附加到教师活动
                    extra_content = step.get("教学内容", "")
                    ppt_ref = step.get("对应PPT页码", "")
                    if extra_content:
                        teacher_act = f"【教学内容】{extra_content}\n{teacher_act}" if teacher_act else str(extra_content)
                    if ppt_ref:
                        teacher_act = f"{teacher_act}\n（PPT: {ppt_ref}）" if teacher_act else f"（PPT: {ppt_ref}）"
                    
                    # 收集其他未知字段
                    known_step_keys = {"环节", "教学环节", "name", "时长", "duration", "时间",
                                       "教师活动", "学生活动", "设计意图", "教学内容", "对应PPT页码"}
                    for sk, sv in step.items():
                        if sk not in known_step_keys and sv:
                            extra = self._plain_block(sv)
                            if extra:
                                teacher_act = f"{teacher_act}\n{sk}：{extra}" if teacher_act else f"{sk}：{extra}"
                    
                    self._set_cell(row.cells[0], step_name, bold=True)
                    self._set_cell(row.cells[1], step_time if step_time else "")
                    self._set_cell(row.cells[2], teacher_act if teacher_act else "")
                    self._set_cell(row.cells[3], student_act if student_act else "")
                    self._set_cell(row.cells[4], design_intent if design_intent else "")
                else:
                    self._set_cell(row.cells[0], step)
            self._repeat_header(process_table.rows[0])
            self._fix_layout(process_table)
        elif isinstance(process, dict):
            self._add_dict_or_list_content(doc, process)
        else:
            p = doc.add_paragraph()
            run = p.add_run("（请根据实际情况设计教学过程）")
            run.font.size = Pt(self._SZ_BODY)
            self._set_cn_font(run, '宋体')
        
        # ========== 板书设计/课件框架 ==========
        board = lesson_plan.get("板书设计/课件框架", lesson_plan.get("板书设计", {}))
        if board:
            self._add_section_heading(doc, "六、板书设计/课件框架")
            self._add_dict_or_list_content(doc, board)
        
        # ========== 作业布置与课后拓展 ==========
        homework = lesson_plan.get("作业布置与课后拓展", {})
        if homework:
            self._add_section_heading(doc, "七、作业布置与课后拓展")
            self._add_dict_or_list_content(doc, homework)
        
        # ========== 教学反思与应急预案 ==========
        reflection = lesson_plan.get("教学反思与应急预案", {})
        if reflection:
            self._add_section_heading(doc, "八、教学反思与应急预案")
            self._add_dict_or_list_content(doc, reflection)
        
        # ========== 高校专属模块 ==========
        university_modules = [
            ("教案头部合规信息", "附录A"),
            ("OBE成果导向课程目标对标", "附录B"),
            ("课程思政专业级融入点", "附录C"),
            ("学术前沿与科研素养培养", "附录D"),
            ("形成性评价与毕业要求达成度设计", "附录E"),
        ]
        for module_name, appendix_label in university_modules:
            content = lesson_plan.get(module_name, {})
            if content:
                self._add_section_heading(doc, f"{appendix_label}、{module_name}")
                self._add_dict_or_list_content(doc, content)
        
        # ========== 其他未处理的模块 ==========
        handled_keys = {
            "教案基本信息", "教学目标", "教学重难点", "教学准备",
            "教学过程设计", "板书设计/课件框架", "板书设计",
            "作业布置与课后拓展", "教学反思与应急预案",
            "教案头部合规信息", "OBE成果导向课程目标对标",
            "课程思政专业级融入点", "学术前沿与科研素养培养",
            "形成性评价与毕业要求达成度设计",
        }
        extra_idx = 0
        for key, value in lesson_plan.items():
            if key not in handled_keys and value:
                extra_idx += 1
                self._add_section_heading(doc, f"补充模块{extra_idx}、{key}")
                self._add_dict_or_list_content(doc, value)
        
        # ========== 保存文件 ==========
        sanitized_topic = re.sub(r'[\\/:*?"<>|]', '_', topic)
        filename = f"{sanitized_topic}_教案.docx"
        file_path = os.path.join(output_dir, filename)
        doc.save(file_path)
        
        return file_path
    
    @classmethod
    def _group_goals(cls, goals):
        """把「教学目标」整理成 [(维度, [目标...]), ...]，**不预设维度名称**。

        为什么不做成固定三维：2022 年版义务教育课程方案与课程标准已把课程目标
        从"三维目标"转为"课程核心素养"，不同学科维度不同（语文：文化自信/语言
        运用/思维能力/审美创造；历史：唯物史观/时空观念/史料实证/历史解释/家国
        情怀）。硬编码三维既与现行课标不符，也会把模型返回的素养维度错误归并。

        输入容错（模型输出形态不固定，这层必须宽容）：
          {"文化自信": [...], "语言运用": [...]}          → 每项一个维度
          [{"维度": "文化自信", "内容": [...]} , ...]      → 按维度分组
          ["能正确读写…", "能概括…"]                      → 归入"教学目标"
          list[dict] 无维度字段                            → 归入"教学目标"
        """
        from collections import OrderedDict

        grouped: "OrderedDict[str, list]" = OrderedDict()

        def _add(dim, value):
            dim = cls._plain_scalar(dim) or "教学目标"
            bucket = grouped.setdefault(dim, [])
            # 走 _flatten 而不是 str()：模型有时把一条目标写成
            # {"具体目标": "能说出…"}，str() 会把 repr 直接送进 Word
            # （历史事故：目标表格里出现 `{'具体目标': "能准确说出…`）
            for _lv, text in cls._flatten(value):
                if text.strip():
                    bucket.append(text.strip())

        if isinstance(goals, dict):
            for dim, value in goals.items():
                _add(dim, value)
        elif isinstance(goals, (list, tuple)):
            for goal in goals:
                if isinstance(goal, dict):
                    dim = (goal.get("维度") or goal.get("类型")
                           or goal.get("category") or goal.get("素养") or "")
                    if dim:
                        body = (goal.get("内容") or goal.get("目标")
                                or goal.get("content") or goal.get("描述") or "")
                        # 有维度时，若内容为空则退化成整条渲染，避免丢内容
                        _add(dim, body if body else goal)
                    else:
                        _add("教学目标", goal)
                else:
                    _add("教学目标", goal)
        elif goals:
            _add("教学目标", goals)

        if not grouped:
            grouped["教学目标"] = []
        return list(grouped.items())

    def _add_section_heading(self, doc, text: str):
        """添加章节标题"""
        from docx.shared import Pt, RGBColor
        
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(16)
        p.paragraph_format.space_after = Pt(8)
        p.paragraph_format.keep_with_next = True  # 标题不与正文分离到两页
        run = p.add_run(str(text))
        run.bold = True
        run.font.size = Pt(self._SZ_H2)
        run.font.color.rgb = RGBColor(0x1A, 0x5C, 0xA8)
        self._set_cn_font(run, '黑体')

    def _add_sub_heading(self, doc, text: str):
        """小节标题（板书要点、课后作业这类）"""
        from docx.shared import Pt, RGBColor

        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(str(text))
        run.bold = True
        run.font.size = Pt(self._SZ_H3)
        run.font.color.rgb = RGBColor(0x33, 0x33, 0x33)
        self._set_cn_font(run, '黑体')

    def _add_bullet(self, doc, text: str, level: int = 0):
        """真正的项目符号段落：悬挂缩进让换行对齐，而不是靠空格硬凑。

        原实现写 `p.add_run(f"- {item}")`，多行内容只能靠空格模拟层级
        （文档里真的出现过 "-    单位：…"）。这里用「符号 + 悬挂缩进」，
        换行会自动与首行文字对齐，层级用缩进表达。
        """
        from docx.shared import Pt, Cm

        marker = ("•", "◦", "▪")[min(level, 2)]
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.left_indent = Cm(0.74 + 0.6 * level)
        pf.first_line_indent = Cm(-0.4)   # 负首行 = 悬挂，换行后与文字左对齐
        pf.space_after = Pt(2)
        pf.line_spacing = 1.4
        run = p.add_run(f"{marker} {text}")
        run.font.size = Pt(self._SZ_BODY)
        self._set_cn_font(run, '宋体')

    def _add_numbered_item(self, doc, num: int, text: str):
        """添加编号项"""
        from docx.shared import Pt, Cm

        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.74)
        p.paragraph_format.first_line_indent = Cm(-0.55)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = 1.4
        run = p.add_run(f"{num}. {text}")
        run.font.size = Pt(self._SZ_BODY)
        self._set_cn_font(run, '宋体')

    def _set_header_cell(self, cell, text: str, width=None):
        """设置表头单元格（深蓝底白色粗体）"""
        from docx.shared import Pt, RGBColor
        from docx.oxml.ns import nsdecls
        from docx.oxml import parse_xml
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        
        cell.text = ""
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.line_spacing = 1.15
        run = p.add_run(str(text))
        run.bold = True
        run.font.size = Pt(self._SZ_TABLE)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        self._set_cn_font(run, '黑体')
        shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="1A5CA8"/>')
        cell._tc.get_or_add_tcPr().append(shading)
        if width:
            cell.width = width

    @staticmethod
    def _repeat_header(row):
        """让表头在跨页时重复。

        长表格（教学过程最常跨页）翻到第二页就只剩正文，读者得回头找列标题。
        这是 `<w:tblHeader/>` 一句话的事，但不做的话没人会报错。
        """
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
        tr_pr = row._tr.get_or_add_trPr()
        if tr_pr.find(qn('w:tblHeader')) is None:
            el = OxmlElement('w:tblHeader')
            el.set(qn('w:val'), 'true')
            tr_pr.append(el)

    @staticmethod
    def _fix_layout(table):
        """关掉自动伸缩：开启时 Word 会按内容重排列宽，5 列的表格会被挤成一团。"""
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
        tbl_pr = table._tbl.tblPr
        for tag in ('w:tblLayout',):
            existing = tbl_pr.find(qn(tag))
            if existing is not None:
                tbl_pr.remove(existing)
        layout = OxmlElement('w:tblLayout')
        layout.set(qn('w:type'), 'fixed')
        tbl_pr.append(layout)

    def _set_cell(self, cell, content, bold: bool = False, bg_color: str = None, width=None,
                  size=None, first_line_indent=None):
        """设置表格单元格。

        `content` 可以是任意形状（str / list / dict）—— 一律先过 `_plain_block`
        摊成可读文本。**绝不**直接 str() 一个复合结构：那会把 Python 的 repr
        写进文档（历史事故：教学目标格里出现 `{'具体目标': …`）。
        """
        from docx.shared import Pt
        from docx.oxml.ns import nsdecls
        from docx.oxml import parse_xml

        text = content if isinstance(content, str) else self._plain_block(content)
        cell.text = ""
        p = cell.paragraphs[0]
        # 表格里按 1.15 倍行距：1.5 在窄列里会被拆得七零八落
        p.paragraph_format.line_spacing = 1.15
        p.paragraph_format.space_after = Pt(2)
        run = p.add_run(text)
        run.font.size = Pt(size or self._SZ_TABLE)
        self._set_cn_font(run, '宋体')
        if bold:
            run.bold = True
        if bg_color:
            shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{bg_color}"/>')
            cell._tc.get_or_add_tcPr().append(shading)
        if width:
            cell.width = width
    
    def _add_dict_or_list_content(self, doc, content):
        """把「板书设计 / 作业布置 / 教学反思」这类模块渲染进正文。

        统一走 `_flatten` 得到 (层级, 文本)，再用 `_add_bullet` 排版：
          - 键用小节标题（黑体四号），值按其形状铺成条目；
          - 条目用真项目符号 + 悬挂缩进，**不用** `- ` 加空格硬凑缩进
            （原实现里出现过 "-    单位：…"，换行后完全对不起）。
        """
        from docx.shared import Pt

        rows = self._flatten(content)
        if not rows:
            return

        # 顶层且只有一条 → 当小节标题；否则铺完整个模块
        if len(rows) == 1 and rows[0][0] == 0:
            body = rows[0][1]
            # "结构化板书要点：" 这类以冒号收尾的当作标题，正文另起
            if body.endswith(("：", ":")):
                self._add_sub_heading(doc, body.rstrip("：:"))
                return
            p = doc.add_paragraph()
            run = p.add_run(body)
            run.font.size = Pt(self._SZ_BODY)
            self._set_cn_font(run, '宋体')
            return

        for level, text in rows:
            if level == 0 and text.endswith(("：", ":")):
                self._add_sub_heading(doc, text.rstrip("：:"))
                continue
            if level == 0 and self._looks_like_key(text):
                # 顶层「键：值」—— 键交给小节标题，值单独一条
                key, _, value = text.partition("：")
                self._add_sub_heading(doc, key)
                if value.strip():
                    self._add_bullet(doc, value.strip())
                continue
            self._add_bullet(doc, text, level)

    @staticmethod
    def _looks_like_key(text: str) -> bool:
        """顶层「XX：……」，且键足够短 —— 短到像字段名而不是一整句正文"""
        key, sep, value = text.partition("：")
        return bool(sep) and 0 < len(key) <= 12 and bool(value.strip())
    
    @staticmethod
    def _set_cn_font(run, east_asian='宋体', western='Times New Roman'):
        """安全地设置中英文字体"""
        from docx.oxml.ns import qn
        run.font.name = western  # 这会自动创建rPr和rFonts元素
        run._element.rPr.rFonts.set(qn('w:eastAsia'), east_asian)
    
    def generate_from_ppt(self, ppt_content: str, level: str, subject: str, 
                         grade: str, topic: str, duration: int) -> Dict[str, Any]:
        """从PPT生成匹配的教案"""
        try:
            # 1. 构建PPT匹配Prompt
            prompt = self.prompts.PPT_MATCHING_TEMPLATE.format(
                level=level,
                subject=subject,
                grade=grade,
                topic=topic,
                duration=duration,
                ppt_content=ppt_content
            )
            
            # 2. 调用LLM生成教案
            response = llm_service.chat(prompt)
            
            # 3. 解析生成的内容
            lesson_plan = self._parse_lesson_plan(response)
            
            return lesson_plan
            
        except Exception as e:
            raise Exception(f"从PPT生成教案失败: {str(e)}")
    
    # 辅助方法
    def _get_level_rules(self, level: str) -> Dict[str, Any]:
        """获取学段适配规则"""
        level_rules = {
            "小学": {
                "core_modules": ["核心素养对标", "趣味互动与课堂管控设计", "分层教学要求", "德育与习惯养成融入点"],
                "language_style": "通俗易懂、生动形象，多用具象化案例",
                "interaction_ratio": 0.3,
                "max_section_duration": 10
            },
            "初中": {
                "core_modules": ["核心素养与中考对标", "思维能力培养设计", "分层教学与学困生帮扶", "探究式学习环节"],
                "language_style": "兼顾基础知识点巩固与中考考点衔接",
                "interaction_ratio": 0.2,
                "max_section_duration": 15
            },
            "普通高中": {
                "core_modules": ["学科核心素养与高考对标", "学业质量评价标准", "重难点突破与深度学习设计", "学业水平考试/高考适配设计"],
                "language_style": "贴合高中深度学习要求，逻辑严谨，知识点体系化",
                "interaction_ratio": 0.15,
                "max_section_duration": 20
            },
            "职业高中/中等职业学校": {
                "core_modules": ["岗课赛证对标", "职业素养融入点", "技能实训环节设计", "企业真实案例融入"],
                "language_style": "以岗位技能为核心，理论教学服务于实操能力培养",
                "interaction_ratio": 0.4,
                "max_section_duration": 15
            },
            "普通高等院校": {
                "core_modules": ["教案头部合规信息", "OBE成果导向课程目标对标", "课程思政专业级融入点", "学术前沿与科研素养培养", "形成性评价与毕业要求达成度设计", "教学过程分环节合规设计", "板书设计/课件核心框架", "课后任务与拓展学习", "教学反思与应急预案"],
                "language_style": "学术严谨，理论与实践结合，融入前沿内容",
                "interaction_ratio": 0.25,
                "max_section_duration": 25
            }
        }
        return level_rules.get(level, level_rules["小学"])
    
    def _get_subject_rules(self, level: str, subject: str) -> Dict[str, Any]:
        """获取学科/专业适配规则"""
        # 大学专业特殊处理
        if level == "普通高等院校":
            return self.university_config.get_major_config(subject)
        
        # 其他学段的学科规则
        subject_rules = {
            "语文": {
                "core_competencies": ["语言建构与运用", "思维发展与提升", "审美鉴赏与创造", "文化传承与理解"],
                "teaching_focus": "阅读与写作能力培养"
            },
            "数学": {
                "core_competencies": ["数学抽象", "逻辑推理", "数学建模", "直观想象", "数学运算", "数据分析"],
                "teaching_focus": "逻辑思维与问题解决能力"
            },
            "英语": {
                "core_competencies": ["语言能力", "文化意识", "思维品质", "学习能力"],
                "teaching_focus": "听说读写综合能力"
            },
            "物理": {
                "core_competencies": ["物理观念", "科学思维", "科学探究", "科学态度与责任"],
                "teaching_focus": "实验探究与科学思维"
            },
            "化学": {
                "core_competencies": ["宏观辨识与微观探析", "变化观念与平衡思想", "证据推理与模型认知", "科学探究与创新意识", "科学态度与社会责任"],
                "teaching_focus": "实验操作与科学探究"
            },
            "生物": {
                "core_competencies": ["生命观念", "科学思维", "科学探究", "社会责任"],
                "teaching_focus": "实验探究与生命观念"
            },
            "历史": {
                "core_competencies": ["唯物史观", "时空观念", "史料实证", "历史解释", "家国情怀"],
                "teaching_focus": "历史思维与家国情怀"
            },
            "地理": {
                "core_competencies": ["人地协调观", "综合思维", "区域认知", "地理实践力"],
                "teaching_focus": "空间思维与地理实践"
            },
            "道德与法治": {
                "core_competencies": ["政治认同", "科学精神", "法治意识", "公共参与"],
                "teaching_focus": "价值观培养与法治意识"
            },
            "音乐": {
                "core_competencies": ["审美感知", "艺术表现", "文化理解"],
                "teaching_focus": "音乐素养与审美能力"
            },
            "美术": {
                "core_competencies": ["图像识读", "美术表现", "审美判断", "创意实践", "文化理解"],
                "teaching_focus": "艺术素养与创造力"
            },
            "体育与健康": {
                "core_competencies": ["运动能力", "健康行为", "体育品德"],
                "teaching_focus": "身体素质与健康意识"
            }
        }
        return subject_rules.get(subject, {
            "core_competencies": [],
            "teaching_focus": "综合能力培养"
        })
    
    def _define_core_goals(self, topic: str, level: str, subject: str) -> List[str]:
        """定义核心教学目标"""
        # 这里可以通过LLM生成更具体的目标
        return [
            f"掌握{topic}的基本概念和原理",
            f"培养学生对{subject}的兴趣和探究精神",
            f"提高学生解决与{topic}相关问题的能力"
        ]
    
    def _define_knowledge_scope(self, topic: str, level: str, subject: str) -> List[str]:
        """定义知识点范围"""
        # 这里可以通过LLM生成更具体的知识点
        return [
            f"{topic}的基本概念",
            f"{topic}的核心原理",
            f"{topic}的应用实例",
            f"{topic}与其他知识点的联系"
        ]
    
    def _validate_compliance(self, level: str, subject: str, topic: str) -> Dict[str, Any]:
        """合规性校验"""
        # 简单的合规性检查
        return {
            "compliance": "通过",
            "issues": []
        }
    
    def _define_modules(self, level: str, subject: str) -> List[str]:
        """定义模块结构"""
        # 通用模块
        modules = [
            "教案基本信息",
            "教学目标",
            "教学重难点",
            "教学准备",
            "教学过程设计",
            "板书设计/课件框架",
            "作业布置与课后拓展",
            "教学反思与应急预案"
        ]
        
        # 添加学段专属模块
        level_rules = self._get_level_rules(level)
        modules.extend(level_rules.get("core_modules", []))
        
        return modules
    
    def _define_sections(self, level: str, duration: int) -> List[str]:
        """划分教学环节"""
        if duration <= 30:
            return ["导入", "新知讲解", "练习巩固", "总结"]
        elif duration <= 45:
            return ["导入", "新知讲解", "小组讨论", "练习巩固", "总结"]
        else:
            return ["导入", "新知讲解", "实验/实践", "小组讨论", "练习巩固", "总结"]
    
    def _allocate_time(self, sections: List[str], duration: int) -> Dict[str, int]:
        """分配时长"""
        time_allocation = {}
        section_count = len(sections)
        base_time = duration // section_count
        remainder = duration % section_count
        
        for i, section in enumerate(sections):
            time_allocation[section] = base_time + (1 if i < remainder else 0)
        
        return time_allocation
    
    def _define_course_goals(self, topic: str, subject: str) -> List[Dict[str, Any]]:
        """定义课程目标（大学专用）"""
        major_config = self.university_config.get_major_config(subject)
        return [
            {
                "goal": f"掌握{topic}的基本概念和理论基础",
                "graduate_requirement": "具备扎实的专业基础知识",
                "assessment_method": "课堂测验、作业"
            },
            {
                "goal": f"能够应用{topic}的原理解决实际问题",
                "graduate_requirement": "具备解决复杂工程问题的能力",
                "assessment_method": "实验报告、项目设计"
            },
            {
                "goal": f"了解{topic}的前沿发展和应用前景",
                "graduate_requirement": "具备终身学习能力",
                "assessment_method": "文献综述、课堂讨论"
            }
        ]
    
    def _select_prompt_template(self, level: str, subject: str) -> str:
        """选择合适的Prompt模板（参数均为 ALL_LEVELS_BASIC_TEMPLATE 所需字段）"""
        return self.prompts.ALL_LEVELS_BASIC_TEMPLATE
    
    def _parse_lesson_plan(self, response: str) -> Dict[str, Any]:
        """解析生成的教案内容"""
        try:
            # 提取JSON部分
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                lesson_plan = json.loads(json_match.group(0))
                return lesson_plan
            else:
                # 如果没有找到JSON，返回一个基本结构
                return {
                    "教案基本信息": {},
                    "教学目标": [],
                    "教学重难点": {},
                    "教学准备": {},
                    "教学过程设计": [],
                    "板书设计/课件框架": {},
                    "作业布置与课后拓展": {},
                    "教学反思与应急预案": {}
                }
        except Exception:
            # 解析失败时返回基本结构
            return {
                "教案基本信息": {},
                "教学目标": [],
                "教学重难点": {},
                "教学准备": {},
                "教学过程设计": [],
                "板书设计/课件框架": {},
                "作业布置与课后拓展": {},
                "教学反思与应急预案": {}
            }
    
    def _parse_modification_result(self, response: str) -> Dict[str, Any]:
        """解析修改结果"""
        try:
            # 提取JSON部分
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                result = json.loads(json_match.group(0))
                return result
            else:
                return {
                    "modified_lesson_plan": {},
                    "ppt_modification_suggestions": [],
                    "change_log": [],
                    "version": "1.0"
                }
        except Exception:
            return {
                "modified_lesson_plan": {},
                "ppt_modification_suggestions": [],
                "change_log": [],
                "version": "1.0"
            }
    
    def _ensure_content_completeness(self, lesson_plan: Dict[str, Any], level: str, subject: str) -> Dict[str, Any]:
        """确保内容完整性"""
        # 检查并补充必要模块
        required_modules = [
            "教案基本信息",
            "教学目标",
            "教学重难点",
            "教学准备",
            "教学过程设计",
            "板书设计/课件框架",
            "作业布置与课后拓展",
            "教学反思与应急预案"
        ]
        
        for module in required_modules:
            if module not in lesson_plan:
                lesson_plan[module] = {} if module not in ["教学目标", "教学过程设计"] else []
            elif module == "教学目标" and not isinstance(lesson_plan[module], list):
                # 模型常把教学目标输出成 dict（如 {"文化自信": [...]}）。
                # 下游 _normalize_goals 有专门的 dict 分支、能按素养维度正确分组，
                # 故有内容时保留原样即可。
                # 原逻辑一律置空，会把整块教学目标丢掉（表现为"教学目标为空"）。
                value = lesson_plan[module]
                if isinstance(value, str):
                    lesson_plan[module] = [value.strip()] if value.strip() else []
                elif not value:
                    lesson_plan[module] = []
            elif module == "教学过程设计" and not isinstance(lesson_plan[module], list):
                # 下游按 list 逐行渲染教学环节表格，故 dict/str 需适配成 list；
                # 同样必须保住已有内容，不能一丢了之。
                value = lesson_plan[module]
                if isinstance(value, dict) and value:
                    lesson_plan[module] = [{k: v} for k, v in value.items()]
                elif isinstance(value, str) and value.strip():
                    lesson_plan[module] = [value.strip()]
                elif not value:
                    lesson_plan[module] = []
        
        # 大学专业特殊模块
        if level == "普通高等院校":
            university_modules = [
                "教案头部合规信息",
                "OBE成果导向课程目标对标",
                "课程思政专业级融入点",
                "学术前沿与科研素养培养",
                "形成性评价与毕业要求达成度设计"
            ]
            
            for module in university_modules:
                if module not in lesson_plan:
                    lesson_plan[module] = {}
        
        return lesson_plan
    
    def _validate_norm_compliance(self, lesson_plan: Dict[str, Any], level: str, subject: str) -> List[Dict[str, Any]]:
        """规范合规性校验"""
        issues = []
        
        # 检查必填模块
        required_modules = [
            "教案基本信息",
            "教学目标",
            "教学重难点",
            "教学准备",
            "教学过程设计",
            "板书设计/课件框架",
            "作业布置与课后拓展",
            "教学反思与应急预案"
        ]
        
        for module in required_modules:
            if module not in lesson_plan or not lesson_plan[module]:
                issues.append({
                    "type": "规范合规性",
                    "severity": "严重",
                    "message": f"缺少必填模块: {module}"
                })
        
        # 大学专业特殊检查
        if level == "普通高等院校":
            university_modules = [
                "教案头部合规信息",
                "OBE成果导向课程目标对标",
                "课程思政专业级融入点",
                "学术前沿与科研素养培养",
                "形成性评价与毕业要求达成度设计"
            ]
            
            for module in university_modules:
                if module not in lesson_plan or not lesson_plan[module]:
                    issues.append({
                        "type": "规范合规性",
                        "severity": "严重",
                        "message": f"大学教案缺少必填模块: {module}"
                    })
        
        return issues
    
    def _validate_content_professionalism(self, lesson_plan: Dict[str, Any], level: str, subject: str) -> List[Dict[str, Any]]:
        """内容专业性校验"""
        issues = []
        
        # 简单的内容检查
        if "教学目标" in lesson_plan and isinstance(lesson_plan["教学目标"], list):
            if len(lesson_plan["教学目标"]) < 3:
                issues.append({
                    "type": "内容专业性",
                    "severity": "警告",
                    "message": "教学目标数量不足，建议至少3个"
                })
        
        if "教学过程设计" in lesson_plan and isinstance(lesson_plan["教学过程设计"], list):
            if len(lesson_plan["教学过程设计"]) < 3:
                issues.append({
                    "type": "内容专业性",
                    "severity": "警告",
                    "message": "教学环节数量不足，建议至少3个"
                })
        
        return issues
    
    def _generate_correction_plan(self, issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """生成修正方案"""
        correction_plan = []
        
        for issue in issues:
            message = issue["message"]
            # 处理消息中没有冒号的情况
            if ':' in message:
                content = message.split(':', 1)[1].strip()
                suggestion = f"请补充或完善{content}"
            else:
                suggestion = f"请处理: {message}"
            
            correction_plan.append({
                "issue": message,
                "suggestion": suggestion
            })
        
        return correction_plan
    
    def _generate_optimization_suggestions(self, lesson_plan: Dict[str, Any], level: str, subject: str) -> List[str]:
        """生成优化建议"""
        suggestions = []
        
        if level == "小学":
            suggestions.append("建议增加更多互动游戏，提高学生参与度")
            suggestions.append("教学语言应更加生动形象，适合小学生认知水平")
        elif level == "初中":
            suggestions.append("建议增加探究式学习环节，培养学生的思维能力")
            suggestions.append("教学内容应兼顾基础知识点与中考考点")
        elif level == "普通高中":
            suggestions.append("建议加强重难点突破方法的设计")
            suggestions.append("教学内容应贴合高中深度学习要求")
        elif level == "职业高中/中等职业学校":
            suggestions.append("建议增加更多真实企业案例和实训环节")
            suggestions.append("教学内容应更加贴近岗位实际需求")
        elif level == "普通高等院校":
            suggestions.append("建议进一步强化OBE成果导向的课程目标设计")
            suggestions.append("建议增加更多学术前沿内容和科研素养培养环节")
            suggestions.append("建议完善课程思政的专业级融入设计")
        
        return suggestions
    
    def _auto_correct_lesson_plan(self, lesson_plan: Dict[str, Any], correction_plan: List[Dict[str, Any]]) -> Dict[str, Any]:
        """自动修正教案"""
        # 简单的自动修正
        for correction in correction_plan:
            issue = correction["issue"]
            if "缺少必填模块" in issue:
                module_name = issue.split(':', 1)[1].strip()
                lesson_plan[module_name] = {} if "目标" not in module_name and "过程" not in module_name else []
        
        return lesson_plan
    
    def _generate_version_number(self) -> str:
        """生成版本号"""
        return f"{time.strftime('%Y%m%d')}.{int(time.time() % 1000)}"
