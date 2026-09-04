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
    
    def __init__(self):
        """初始化教案生成器"""
        self.prompts = LessonPlanPrompts()
        self.university_config = UniversityMajorConfig()
    
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
        
        # ========== 设置页面边距 ==========
        for section in doc.sections:
            section.top_margin = Cm(2.5)
            section.bottom_margin = Cm(2.5)
            section.left_margin = Cm(3)
            section.right_margin = Cm(3)
        
        # ========== 设置默认字体 ==========
        style = doc.styles['Normal']
        font = style.font
        font.name = 'Times New Roman'
        font.size = Pt(12)
        style.element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
        style.paragraph_format.line_spacing = 1.5
        
        # ========== 提取基本信息 ==========
        basic_info = lesson_plan.get("教案基本信息", {})
        # 优先使用传入的topic参数，确保文件名与用户输入一致
        if not topic:
            topic = basic_info.get("课题", basic_info.get("教学主题", "教案"))
        
        # ========== 标题 ==========
        title_para = doc.add_paragraph()
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_run = title_para.add_run(f"{topic}")
        title_run.bold = True
        title_run.font.size = Pt(22)
        title_run.font.color.rgb = RGBColor(0x1A, 0x5C, 0xA8)
        self._set_cn_font(title_run, '黑体')
        
        subtitle_para = doc.add_paragraph()
        subtitle_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        subtitle_run = subtitle_para.add_run("教 案")
        subtitle_run.bold = True
        subtitle_run.font.size = Pt(18)
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
            info_rows.append((label, str(val) if val else "________"))
        
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
            content_text = "\n".join([f"{i+1}. {item}" for i, item in enumerate(cat_items)]) if cat_items else "（请根据实际情况补充）"
            self._set_cell(row.cells[1], content_text)
        
        # ========== 教学重难点（表格）==========
        focus = lesson_plan.get("教学重难点", {})
        self._add_section_heading(doc, "三、教学重难点")
        
        focus_data = {"教学重点": "", "教学难点": "", "突破策略": ""}
        if isinstance(focus, dict):
            for fkey in ["教学重点", "重点"]:
                if fkey in focus:
                    val = focus[fkey]
                    focus_data["教学重点"] = "\n".join([f"- {v}" for v in val]) if isinstance(val, list) else str(val)
                    break
            for fkey in ["教学难点", "难点"]:
                if fkey in focus:
                    val = focus[fkey]
                    focus_data["教学难点"] = "\n".join([f"- {v}" for v in val]) if isinstance(val, list) else str(val)
                    break
            for fkey in ["突破策略", "重难点突破", "突破方法", "解决策略"]:
                if fkey in focus:
                    val = focus[fkey]
                    focus_data["突破策略"] = "\n".join([f"- {v}" for v in val]) if isinstance(val, list) else str(val)
                    break
            # 收集未匹配的内容
            known_focus = {"教学重点", "重点", "教学难点", "难点", "突破策略", "重难点突破", "突破方法", "解决策略"}
            for k, v in focus.items():
                if k not in known_focus:
                    if not focus_data["突破策略"]:
                        focus_data["突破策略"] = f"{k}：{v}" if not isinstance(v, list) else f"{k}：\n" + "\n".join([f"- {item}" for item in v])
        elif isinstance(focus, str):
            focus_data["教学重点"] = focus
        
        focus_table = doc.add_table(rows=3, cols=2)
        focus_table.style = 'Table Grid'
        focus_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        for idx, (fk, fv) in enumerate(focus_data.items()):
            self._set_cell(focus_table.rows[idx].cells[0], fk, bold=True, bg_color="E8EEF7", width=Cm(3.5))
            self._set_cell(focus_table.rows[idx].cells[1], fv if fv else "（请根据实际情况补充）")
        
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
                    val = preparation[tk]
                    prep_data["教师准备"] = "\n".join([f"- {v}" for v in val]) if isinstance(val, list) else str(val)
                    break
            for sk in student_keys:
                if sk in preparation:
                    val = preparation[sk]
                    prep_data["学生准备"] = "\n".join([f"- {v}" for v in val]) if isinstance(val, list) else str(val)
                    break
            for mk in media_keys:
                if mk in preparation:
                    val = preparation[mk]
                    prep_data["教学媒体"] = "\n".join([f"- {v}" for v in val]) if isinstance(val, list) else str(val)
                    break
            # 未匹配的内容归入教师准备
            matched_prep = set(teacher_keys + student_keys + media_keys)
            extra_items = []
            for k, v in preparation.items():
                if k not in matched_prep:
                    if isinstance(v, list):
                        extra_items.append(f"{k}：" + "、".join([str(item) for item in v]))
                    else:
                        extra_items.append(f"{k}：{v}")
            if extra_items:
                if prep_data["教师准备"]:
                    prep_data["教师准备"] += "\n" + "\n".join(extra_items)
                else:
                    prep_data["教师准备"] = "\n".join(extra_items)
        elif isinstance(preparation, list):
            prep_data["教师准备"] = "\n".join([f"- {item}" for item in preparation])
        elif isinstance(preparation, str):
            prep_data["教师准备"] = preparation
        
        prep_table = doc.add_table(rows=3, cols=2)
        prep_table.style = 'Table Grid'
        prep_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        for idx, (pk, pv) in enumerate(prep_data.items()):
            self._set_cell(prep_table.rows[idx].cells[0], pk, bold=True, bg_color="E8EEF7", width=Cm(3.5))
            self._set_cell(prep_table.rows[idx].cells[1], pv if pv else "（请根据实际情况补充）")
        
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
                            teacher_act = f"{teacher_act}\n{sk}：{sv}" if teacher_act else f"{sk}：{sv}"
                    
                    self._set_cell(row.cells[0], str(step_name), bold=True)
                    self._set_cell(row.cells[1], str(step_time) if step_time else "")
                    self._set_cell(row.cells[2], str(teacher_act) if teacher_act else "")
                    self._set_cell(row.cells[3], str(student_act) if student_act else "")
                    self._set_cell(row.cells[4], str(design_intent) if design_intent else "")
                else:
                    self._set_cell(row.cells[0], str(step))
        elif isinstance(process, dict):
            self._add_dict_or_list_content(doc, process)
        else:
            p = doc.add_paragraph()
            run = p.add_run("（请根据实际情况设计教学过程）")
            run.font.size = Pt(12)
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
    
    @staticmethod
    def _group_goals(goals):
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
            dim = str(dim or "教学目标").strip() or "教学目标"
            bucket = grouped.setdefault(dim, [])
            if isinstance(value, (list, tuple)):
                bucket.extend(str(v) for v in value if str(v).strip())
            elif value is not None and str(value).strip():
                bucket.append(str(value))

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
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(15)
        run.font.color.rgb = RGBColor(0x1A, 0x5C, 0xA8)
        self._set_cn_font(run, '黑体')
    
    def _set_header_cell(self, cell, text: str, width=None):
        """设置表头单元格（深蓝底白色粗体）"""
        from docx.shared import Pt, RGBColor, Cm
        from docx.oxml.ns import nsdecls
        from docx.oxml import parse_xml
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        
        cell.text = ""
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(11)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        self._set_cn_font(run, '黑体')
        shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="1A5CA8"/>')
        cell._tc.get_or_add_tcPr().append(shading)
        if width:
            cell.width = width
    
    def _add_numbered_item(self, doc, num: int, text: str):
        """添加编号项"""
        from docx.shared import Pt
        
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Pt(20)
        run = p.add_run(f"{num}. {text}")
        run.font.size = Pt(12)
        self._set_cn_font(run, '宋体')
    
    def _set_cell(self, cell, text: str, bold: bool = False, bg_color: str = None, width=None):
        """设置表格单元格"""
        from docx.shared import Pt, Cm
        from docx.oxml.ns import nsdecls
        from docx.oxml import parse_xml
        
        cell.text = ""
        p = cell.paragraphs[0]
        run = p.add_run(text)
        run.font.size = Pt(11)
        self._set_cn_font(run, '宋体')
        if bold:
            run.bold = True
        if bg_color:
            shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{bg_color}"/>')
            cell._tc.get_or_add_tcPr().append(shading)
        if width:
            cell.width = width
    
    def _add_dict_or_list_content(self, doc, content):
        """将字典或列表内容添加到文档"""
        from docx.shared import Pt
        
        if isinstance(content, dict):
            for k, v in content.items():
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Pt(10)
                run_label = p.add_run(f"{k}：")
                run_label.bold = True
                run_label.font.size = Pt(12)
                self._set_cn_font(run_label, '黑体')
                
                if isinstance(v, list):
                    for item in v:
                        sub_p = doc.add_paragraph()
                        sub_p.paragraph_format.left_indent = Pt(30)
                        sub_run = sub_p.add_run(f"- {item}")
                        sub_run.font.size = Pt(11)
                        self._set_cn_font(sub_run, '宋体')
                elif isinstance(v, dict):
                    for sub_k, sub_v in v.items():
                        sub_p = doc.add_paragraph()
                        sub_p.paragraph_format.left_indent = Pt(30)
                        sub_run = sub_p.add_run(f"{sub_k}：{sub_v}")
                        sub_run.font.size = Pt(11)
                        self._set_cn_font(sub_run, '宋体')
                else:
                    run_val = p.add_run(str(v))
                    run_val.font.size = Pt(12)
                    self._set_cn_font(run_val, '宋体')
        elif isinstance(content, list):
            for i, item in enumerate(content, 1):
                if isinstance(item, dict):
                    for k, v in item.items():
                        p = doc.add_paragraph()
                        p.paragraph_format.left_indent = Pt(10)
                        run = p.add_run(f"{k}：{v}")
                        run.font.size = Pt(11)
                        self._set_cn_font(run, '宋体')
                else:
                    self._add_numbered_item(doc, i, str(item))
        elif isinstance(content, str):
            p = doc.add_paragraph()
            run = p.add_run(content)
            run.font.size = Pt(12)
            self._set_cn_font(run, '宋体')
    
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
