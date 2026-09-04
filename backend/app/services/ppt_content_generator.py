"""PPT内容生成服务 - 生成标准化的PPT结构化JSON数据"""
import json
import re
from typing import List, Dict, Optional
from .llm_service import llm_service
from .ppt_prompt_templates import PPTPromptTemplates
from .topic_expansion import enrich_for_ppt

# 设计思路参考：清华大学THU-MAIC/OpenMAIC开源项目，核心代码自主实现

class PPTContentGenerator:
    """PPT内容生成器类"""

    def __init__(self):
        """初始化PPT内容生成器"""
        self.prompt_templates = PPTPromptTemplates()

    def prepare_teaching_context(
        self,
        topic: str,
        duration: int,
        audience: str,
        subject: str,
        key_points: list = None,
        reference_docs: list = None,
    ) -> Dict:
        """在用户仅输入主题或要点过少时，自动扩写为可授课的 key_points 与 teaching_content。"""
        return enrich_for_ppt(topic, duration, audience, subject, key_points, reference_docs)

    def generate_ppt_content(self, topic: str, duration: int, audience: str, subject: str,
                           theme_color: str, style_preference: str, key_points: list = None,
                           reference_docs: list = None, template: str = "standard") -> Dict:
        """生成PPT内容"""
        ctx = self.prepare_teaching_context(topic, duration, audience, subject, key_points or [], reference_docs or [])
        key_points_eff = ctx.get("key_points") or []
        teaching_content = ctx.get("teaching_content") or ""
        expansion = ctx.get("expansion") or {}

        # 1. 生成PPT大纲
        outline = self.generate_ppt_outline(
            topic, duration, audience, subject, key_points_eff, teaching_content, expansion=expansion
        )
        
        # 2. 生成视觉风格（直接使用默认值，节省LLM调用）
        visual_style = self._get_default_visual_style(theme_color, style_preference)
        
        # 3. 生成详细内容
        detailed_content = self.generate_detailed_content(
            outline, topic, duration, audience, subject, key_points_eff, teaching_content
        )
        
        return {
            "outline": outline,
            "visual_style": visual_style,
            "detailed_content": detailed_content,
            "metadata": {
                "topic": topic,
                "duration": duration,
                "audience": audience,
                "subject": subject,
                "theme_color": theme_color,
                "style_preference": style_preference,
                "key_points": key_points_eff,
                "teaching_content": teaching_content,
                "topic_expansion": expansion,
                "reference_docs": reference_docs,
                "template": template
            }
        }

    def _is_valid_json(self, response: str) -> bool:
        """检查响应是否是有效的JSON格式"""
        try:
            json.loads(response)
            return True
        except Exception:
            return False

    def _extract_json(self, response: str) -> str:
        """从LLM响应中提取JSON内容（处理markdown代码块等情况）"""
        if not response:
            return response
        text = response.strip()
        # 处理 ```json ... ``` 包裹的情况
        if '```json' in text:
            start = text.find('```json') + 7
            end = text.find('```', start)
            if end > start:
                text = text[start:end].strip()
        elif '```' in text:
            start = text.find('```') + 3
            end = text.find('```', start)
            if end > start:
                text = text[start:end].strip()
        # 尝试找到JSON数组或对象的起始位置
        for i, c in enumerate(text):
            if c in ('{', '['):
                bracket_count = 0
                for j in range(i, len(text)):
                    if text[j] in ('{', '['):
                        bracket_count += 1
                    elif text[j] in ('}', ']'):
                        bracket_count -= 1
                    if bracket_count == 0:
                        return text[i:j+1]
                return text[i:]
        return text

    def _safe_parse_json(self, response: str) -> Optional[any]:
        """安全解析LLM返回的JSON，带提取和容错"""
        if not response:
            return None
        # 先尝试直接解析
        try:
            return json.loads(response)
        except Exception:
            pass
        # 提取后再解析
        cleaned = self._extract_json(response)
        if cleaned:
            try:
                return json.loads(cleaned)
            except Exception:
                pass
        return None

    def _apply_expansion_module_titles(self, outline: List[Dict], expansion: Dict) -> List[Dict]:
        """将扩写得到的知识点模块标题对齐到 knowledge 页。"""
        if not expansion or not isinstance(expansion, dict):
            return outline
        titles = expansion.get("knowledge_modules_for_slides") or []
        if not titles or not isinstance(titles, list):
            return outline
        ti = 0
        for page in outline:
            if page.get("page_type") != "knowledge":
                continue
            if ti >= len(titles):
                break
            title = str(titles[ti]).strip()
            if title:
                page["core_topic"] = title
                co = page.get("content_outline")
                if not co or not isinstance(co, list) or len(co) < 2:
                    page["content_outline"] = [
                        f"{title}：要点与定义",
                        "关键步骤、方法或推理",
                        "课堂示例与辨析",
                        "与前后知识的衔接",
                    ]
            ti += 1
        return outline

    def generate_ppt_outline(self, topic: str, duration: int, audience: str, subject: str, key_points: list = None, teaching_content: str = "", expansion: Dict = None) -> List[Dict]:
        """生成PPT大纲"""
        expansion = expansion or {}
        # 定义教学目标
        teaching_goals = self._define_teaching_goals(topic, audience, subject, key_points, teaching_content)
        
        # 根据课时确定页数
        if duration <= 15:
            page_range = "5-8"
        elif duration <= 30:
            page_range = "8-12"
        elif duration <= 45:
            page_range = "10-15"
        elif duration <= 60:
            page_range = "15-20"
        else:
            page_range = "20-28"
        
        # 生成大纲
        exp_hint = ""
        if expansion:
            mods = expansion.get("knowledge_modules_for_slides") or []
            if mods:
                exp_hint = f"\n【建议知识点页标题序列（尽量采用，可微调）】：{json.dumps(mods, ensure_ascii=False)}"

        prompt = f"""你是一名资深教学课件设计专家。请为以下课程生成PPT大纲。

课程主题：{topic}
目标受众：{audience}
课时时长：{duration}分钟
学科领域：{subject}
核心知识点：{', '.join(key_points) if key_points else '根据主题自动确定'}
教学内容描述：{teaching_content if teaching_content else '根据主题自动生成'}
{exp_hint}

教学目标：
{json.dumps(teaching_goals, ensure_ascii=False)}

要求：
1. PPT总页数在{page_range}页之间
2. 必须包含以下页面类型：cover(封面)、toc(目录)、knowledge(知识点，至少3页)、exercise(互动练习)、summary(总结)
3. 可选包含：extension(拓展资源)
4. 每页的core_topic必须紧扣课程主题"{topic}"，不得偏离；knowledge 页的 core_topic 要**像真实课题名一样具体**（禁止「知识点1」这类占位名）
5. 内容深度必须匹配{audience}的认知水平；content_outline 中每条应是**可展开为幻灯片要点的短句**，不是单词堆砌

请严格以JSON数组格式输出，不要输出其他内容。每个元素包含：page_num(页码)、page_type(类型)、core_topic(核心主题)、content_outline(内容大纲数组，3-5个要点)。

示例格式：
[
  {{"page_num": 1, "page_type": "cover", "core_topic": "课程封面", "content_outline": ["主标题", "副标题", "授课信息"]}},
  {{"page_num": 2, "page_type": "toc", "core_topic": "课程目录", "content_outline": ["模块一", "模块二", "模块三"]}}
]"""
        
        # 使用活跃的LLM提供商生成PPT大纲
        try:
            response = llm_service.chat(prompt, [])
        except Exception as e:
            print(f"LLM生成PPT大纲失败: {e}，使用默认大纲")
            outline = self._generate_default_outline(topic, audience, duration, key_points)
            return self._apply_expansion_module_titles(outline, expansion)
        
        try:
            parsed = self._safe_parse_json(response)
            if parsed and isinstance(parsed, list):
                parsed = self._validate_ppt_outline(parsed, topic, audience, duration)
                return self._apply_expansion_module_titles(parsed, expansion)
            else:
                print(f"大纲解析结果不是列表，使用默认大纲。响应前200字：{str(response)[:200]}")
                o = self._generate_default_outline(topic, audience, duration, key_points)
                return self._apply_expansion_module_titles(o, expansion)
        except Exception as e:
            print(f"解析大纲失败: {e}")
            o = self._generate_default_outline(topic, audience, duration, key_points)
            return self._apply_expansion_module_titles(o, expansion)

    def generate_visual_style(self, topic: str, audience: str, duration: int, subject: str, theme_color: str, style_preference: str) -> Dict:
        """生成视觉风格（直接使用预设值，不浪费LLM调用）"""
        return self._get_default_visual_style(theme_color, style_preference)

    def generate_detailed_content(self, outline: List[Dict], topic: str, duration: int, audience: str, subject: str, key_points: list = None, teaching_content: str = "") -> List[Dict]:
        """生成详细内容"""
        detailed_content = []
        
        for page in outline:
            page_type = page.get("page_type")
            
            if page_type == "cover":
                content = self._generate_cover_content(page, topic, audience, duration, subject, teaching_content)
            elif page_type == "toc":
                content = self._generate_toc_content(page, topic, audience, duration, outline, teaching_content)
            elif page_type == "knowledge":
                content = self._generate_knowledge_content(page, topic, audience, duration, subject, key_points or [], teaching_content)
            elif page_type == "exercise":
                content = self._generate_exercise_content(page, topic, audience, duration, subject, teaching_content)
            elif page_type == "summary":
                content = self._generate_summary_content(page, topic, audience, duration, subject, outline, teaching_content)
            elif page_type == "extension":
                content = self._generate_extension_content(page, topic, audience, duration, subject, teaching_content)
            else:
                content = self._generate_default_content(page, topic, audience, duration, subject, teaching_content)
            
            detailed_content.append(content)
        
        return detailed_content

    def _define_teaching_goals(self, topic: str, audience: str, subject: str, key_points: list, teaching_content: str = "") -> Dict:
        """定义教学目标"""
        prompt = f"""你是一名资深教育专家。请为以下课程定义教学目标。

课程主题：{topic}
目标受众：{audience}
学科领域：{subject}
核心知识点：{', '.join(key_points) if key_points else '根据主题确定'}
教学内容描述：{teaching_content if teaching_content else '根据主题确定'}

请严格以JSON格式输出，包含knowledge_goals(知识目标数组)、ability_goals(能力目标数组)、emotional_goals(情感目标数组)，每个数组2-3个条目。
不要输出任何其他内容，只输出JSON。"""
        
        response = llm_service.chat(prompt, [])
        
        try:
            parsed = self._safe_parse_json(response)
            if parsed and isinstance(parsed, dict):
                return parsed
        except Exception as e:
            print(f"解析教学目标失败: {e}")
        
        # 返回默认目标
        return {
            "knowledge_goals": [f"理解{topic}的核心概念和基本原理", f"掌握{topic}的关键知识点和重要特征"],
            "ability_goals": [f"能够运用{topic}的知识解决实际问题", f"具备{topic}相关的分析和应用能力"],
            "emotional_goals": [f"培养对{topic}领域的学习兴趣和探索精神", f"建立严谨的学习态度"]
        }

    def _validate_ppt_outline(self, outline: List[Dict], topic: str, audience: str, duration: int) -> List[Dict]:
        """验证PPT大纲格式"""
        required_types = ["cover", "toc", "knowledge", "exercise", "summary"]
        
        for required_type in required_types:
            page_types = [page.get("page_type") for page in outline]
            if required_type not in page_types:
                outline = self._add_missing_page(outline, required_type, topic, audience)
        
        # 确保至少有3个知识点页
        page_types = [page.get("page_type") for page in outline]
        knowledge_count = page_types.count("knowledge")
        if knowledge_count < 3:
            for i in range(3 - knowledge_count):
                outline = self._add_missing_page(outline, "knowledge", topic, audience, f"{topic} - 知识点{knowledge_count + i + 1}")
        
        # 重新编号页码
        for i, page in enumerate(outline, 1):
            page["page_num"] = i
        
        return outline

    def _add_missing_page(self, outline: List[Dict], page_type: str, topic: str, audience: str, core_topic: str = None) -> List[Dict]:
        """添加缺失的页面"""
        page_configs = {
            "cover": {
                "core_topic": "课程封面",
                "content_outline": [f"{topic}", f"面向{audience}", "课程介绍", "授课信息"]
            },
            "toc": {
                "core_topic": "课程目录",
                "content_outline": ["课程导入", "核心知识点", "案例分析", "互动练习", "课程总结"]
            },
            "knowledge": {
                "core_topic": core_topic or f"{topic}核心知识点",
                "content_outline": ["核心概念解析", "重要原理与特征", "实际应用场景", "关键注意事项"]
            },
            "exercise": {
                "core_topic": "课堂互动练习",
                "content_outline": ["知识巩固练习", "思考与讨论", "实践操作", "问题解答"]
            },
            "summary": {
                "core_topic": "课程总结与回顾",
                "content_outline": ["核心要点回顾", "学习目标检验", "课后作业布置", "后续学习建议"]
            },
            "extension": {
                "core_topic": "拓展资源与延伸",
                "content_outline": ["推荐阅读", "在线资源", "实践项目", "前沿动态"]
            }
        }
        
        config = page_configs.get(page_type, page_configs["knowledge"])
        new_page = {
            "page_num": len(outline) + 1,
            "page_type": page_type,
            "core_topic": config["core_topic"],
            "content_outline": config["content_outline"]
        }
        
        if page_type == "cover":
            outline.insert(0, new_page)
        elif page_type == "toc":
            for i, page in enumerate(outline):
                if page.get("page_type") != "cover":
                    outline.insert(i, new_page)
                    break
            else:
                outline.append(new_page)
        elif page_type == "summary":
            outline.append(new_page)
        elif page_type == "exercise":
            for i in range(len(outline)-1, -1, -1):
                if outline[i].get("page_type") == "summary":
                    outline.insert(i, new_page)
                    break
            else:
                outline.append(new_page)
        else:
            outline.append(new_page)
        
        return outline

    def _generate_default_outline(self, topic: str, audience: str, duration: int, key_points: list = None) -> List[Dict]:
        """生成默认PPT大纲（当LLM不可用时使用）"""
        # 根据学科自动生成相关内容
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
        
        subject_terms = subject_keywords.get(detected_subject, ["概念", "原理", "应用", "案例"])
        
        # 根据用户提供的知识点生成大纲
        kp_pages = []
        if key_points and len(key_points) > 0:
            for i, kp in enumerate(key_points[:8]):
                kp_pages.append({
                    "page_num": 3 + i,
                    "page_type": "knowledge",
                    "core_topic": kp,
                    "content_outline": [
                        f"{kp}的定义与本质",
                        f"{kp}的核心特征与要素",
                        f"{kp}的实际应用场景",
                        f"{kp}的学习要点与注意事项"
                    ]
                })
        
        if not kp_pages:
            # 没有知识点则用默认的
            kp_pages = [
                {"page_num": 3, "page_type": "knowledge", "core_topic": f"{topic} - 基础概念", "content_outline": [
                    f"{topic}的定义与内涵",
                    f"{topic}的起源与发展",
                    f"{topic}的核心特征",
                    f"{topic}与相关概念的关系"
                ]},
                {"page_num": 4, "page_type": "knowledge", "core_topic": f"{topic} - 核心原理", "content_outline": [
                    f"{topic}的核心原理",
                    f"{topic}的关键要素分析",
                    f"{topic}的运作机制",
                    f"{topic}的理论基础"
                ]},
                {"page_num": 5, "page_type": "knowledge", "core_topic": f"{topic} - 实践应用", "content_outline": [
                    f"{topic}的主要应用场景",
                    f"{topic}的操作方法与步骤",
                    f"{topic}的最佳实践",
                    f"{topic}的常见问题与解决"
                ]},
            ]
            # 根据时长增加更多页
            if duration >= 45:
                kp_pages.append({"page_num": 6, "page_type": "knowledge", "core_topic": f"{topic} - 进阶拓展", "content_outline": [
                    f"{topic}的进阶知识",
                    f"{topic}的行业发展趋势",
                    f"{topic}的前沿研究方向",
                    f"{topic}的深度解析"
                ]})
            if duration >= 60:
                kp_pages.append({"page_num": 7, "page_type": "knowledge", "core_topic": f"{topic} - 案例分析", "content_outline": [
                    f"{topic}的典型案例介绍",
                    f"{topic}案例深入解读",
                    f"{topic}案例经验总结",
                    f"{topic}的启示与思考"
                ]})
        
        n = len(kp_pages)
        outline = [
            {"page_num": 1, "page_type": "cover", "core_topic": "课程封面", "content_outline": [f"{topic}", f"面向{audience}", f"{detected_subject}课程", "授课信息"]},
            {"page_num": 2, "page_type": "toc", "core_topic": "课程目录", "content_outline": [kp.get("core_topic") for kp in kp_pages] + ["互动练习", "课程总结"]},
        ]
        outline.extend(kp_pages)
        # 重新编号
        for i, p in enumerate(outline):
            p["page_num"] = i + 1
        
        exercise_num = len(outline) + 1
        summary_num = exercise_num + 1
        outline.append({"page_num": exercise_num, "page_type": "exercise", "core_topic": "课堂互动练习", "content_outline": [
            f"{topic}知识巩固题",
            f"{topic}思考讨论题",
            f"{topic}实践操作题",
            f"{topic}问题解答"
        ]})
        outline.append({"page_num": summary_num, "page_type": "summary", "core_topic": "课程总结与回顾", "content_outline": [
            f"{topic}核心要点回顾",
            f"{topic}学习目标检验",
            f"{topic}课后作业布置",
            f"{topic}后续学习建议"
        ]})
        
        if duration >= 45:
            outline.append({"page_num": summary_num + 1, "page_type": "extension", "core_topic": "拓展资源", "content_outline": [
                f"{topic}推荐书籍",
                f"{topic}在线学习资源",
                f"{topic}实践项目",
                f"{topic}前沿动态"
            ]})
        
        return outline

    def _generate_cover_content(self, page: Dict, topic: str, audience: str, duration: int, subject: str, teaching_content: str = "") -> Dict:
        """生成封面页内容"""
        prompt = self.prompt_templates.generate_cover_prompt(topic, audience, duration, subject, teaching_content)
        response = llm_service.chat(prompt, [])
        
        try:
            parsed = self._safe_parse_json(response)
            if parsed and isinstance(parsed, dict):
                parsed.update({
                    "page_num": page.get("page_num"),
                    "page_type": page.get("page_type"),
                    "core_topic": page.get("core_topic")
                })
                # 确保关键字段存在
                if "main_title" not in parsed:
                    parsed["main_title"] = topic
                if "subtitle" not in parsed:
                    parsed["subtitle"] = f"面向{audience}的{subject}课程 | {duration}分钟"
                return parsed
        except Exception as e:
            print(f"解析封面页内容失败: {e}")
        
        return {
            "page_num": page.get("page_num"),
            "page_type": page.get("page_type"),
            "core_topic": page.get("core_topic"),
            "main_title": topic,
            "subtitle": f"面向{audience}的{subject}课程 | {duration}分钟",
            "instructor_info": "授课教师",
            "notes": "课程介绍页面"
        }

    def _generate_toc_content(self, page: Dict, topic: str, audience: str, duration: int, outline: List[Dict], teaching_content: str = "") -> Dict:
        """生成目录页内容"""
        # 直接从大纲提取目录项，不需要再调用LLM
        toc_items = [p.get("core_topic") for p in outline if p.get("page_type") not in ["cover", "toc"]]
        return {
            "page_num": page.get("page_num"),
            "page_type": page.get("page_type"),
            "core_topic": page.get("core_topic", "课程目录"),
            "toc_items": toc_items,
            "notes": "课程目录页面"
        }

    def _generate_knowledge_content(self, page: Dict, topic: str, audience: str, duration: int, subject: str, key_points: list, teaching_content: str = "") -> Dict:
        """生成知识点页内容"""
        core_topic = page.get("core_topic")
        content_outline = page.get("content_outline", [])
        
        prompt = f"""你是一名{subject}领域的资深教师。请为PPT课件生成一页关于「{core_topic}」的**可直接放映朗读**的详细教学内容。

课程主题：{topic}
当前页面主题：{core_topic}
目标受众：{audience}
内容大纲提示：{json.dumps(content_outline, ensure_ascii=False)}
用户提供的知识点：{', '.join(key_points) if key_points else '无'}

硬性要求（违反则视为不合格）：
1. key_points：恰好 4-5 条；每条 **28-55 个汉字**，必须包含「定义/条件/步骤/关系/例子」中至少两类信息，禁止只写短语标题（如禁止单独「重要性」三字）
2. case_study：80-180 字，有具体人物/情境/数据之一，与「{core_topic}」直接相关
3. notes：给讲师的提醒：先讲什么、用什么类比、常见追问

内容必须紧扣「{core_topic}」，适合{audience}，专业准确。

请严格以JSON格式输出，不要输出其他内容：
{{"key_points": ["要点1", "要点2", ...], "case_study": "案例内容", "notes": "讲师备注"}}"""
        
        response = llm_service.chat(prompt, [])
        
        try:
            parsed = self._safe_parse_json(response)
            if parsed and isinstance(parsed, dict):
                parsed.update({
                    "page_num": page.get("page_num"),
                    "page_type": page.get("page_type"),
                    "core_topic": core_topic
                })
                # 确保key_points存在且非空
                if "key_points" not in parsed or not parsed["key_points"]:
                    parsed["key_points"] = content_outline if content_outline else [f"{core_topic}的核心概念", f"{core_topic}的重要特征", f"{core_topic}的应用方法"]
                if "case_study" not in parsed or not parsed["case_study"]:
                    parsed["case_study"] = f"在实际{subject}教学中，{core_topic}的应用案例。"
                return parsed
        except Exception as e:
            print(f"解析知识点页内容失败: {e}")
        
        return {
            "page_num": page.get("page_num"),
            "page_type": page.get("page_type"),
            "core_topic": core_topic,
            "key_points": content_outline if content_outline else [f"{core_topic}的核心概念", f"{core_topic}的重要特征", f"{core_topic}的应用场景", f"{core_topic}的注意事项"],
            "case_study": f"在{subject}领域中，{core_topic}有着广泛的应用。通过实际案例可以帮助{audience}更好地理解和掌握这一知识点。",
            "notes": f"重点讲解{core_topic}的核心概念，结合案例帮助学生理解。"
        }

    def _generate_exercise_content(self, page: Dict, topic: str, audience: str, duration: int, subject: str, teaching_content: str = "") -> Dict:
        """生成互动习题页内容"""
        prompt = f"""你是一名{subject}领域的资深教师。请为"{topic}"课程生成课堂互动练习题。

课程主题：{topic}
目标受众：{audience}
学科领域：{subject}
本课教学内容与要点（命题必须据此设计，禁止空泛）：{teaching_content[:2000] if teaching_content else "（结合主题具体命制）"}

要求：
1. 生成3道练习题（2道选择题+1道简答题）
2. 选择题包含：question(题干)、options(4个选项数组)、answer(正确答案)
3. 简答题包含：question(题干)、answer(参考答案)
4. 难度匹配{audience}的认知水平
5. 题目紧扣"{topic}"课程内容

请严格以JSON格式输出：
{{"exercises": [{{"question": "题目", "options": ["A. xxx", "B. xxx", "C. xxx", "D. xxx"], "answer": "正确选项"}}, ...], "notes": "教师备注"}}"""
        
        response = llm_service.chat(prompt, [])
        
        try:
            parsed = self._safe_parse_json(response)
            if parsed and isinstance(parsed, dict):
                parsed.update({
                    "page_num": page.get("page_num"),
                    "page_type": page.get("page_type"),
                    "core_topic": page.get("core_topic")
                })
                if "exercises" in parsed and isinstance(parsed["exercises"], list) and len(parsed["exercises"]) > 0:
                    return parsed
        except Exception as e:
            print(f"解析互动习题页内容失败: {e}")
        
        return {
            "page_num": page.get("page_num"),
            "page_type": page.get("page_type"),
            "core_topic": page.get("core_topic"),
            "exercises": [
                {
                    "question": f"关于{topic}，以下哪项描述是正确的？",
                    "options": [f"A. {topic}的基本概念描述", f"B. {topic}的错误理解", f"C. {topic}的常见误区", f"D. {topic}的片面描述"],
                    "answer": f"A. {topic}的基本概念描述"
                },
                {
                    "question": f"{topic}在实际应用中最重要的特点是什么？",
                    "options": ["A. 实用性强", "B. 理论深奥", "C. 操作复杂", "D. 适用面窄"],
                    "answer": "A. 实用性强"
                },
                {
                    "question": f"请简述{topic}的核心要点及其在实际中的应用。",
                    "answer": f"请结合课堂所学，从概念、原理、应用三个方面进行阐述。"
                }
            ],
            "notes": f"通过练习巩固{topic}核心知识，鼓励学生积极参与讨论。"
        }

    def _generate_summary_content(self, page: Dict, topic: str, audience: str, duration: int, subject: str, outline: List[Dict], teaching_content: str = "") -> Dict:
        """生成总结页内容"""
        knowledge_pages = [p for p in outline if p.get("page_type") == "knowledge"]
        knowledge_topics = [p.get("core_topic") for p in knowledge_pages]
        
        prompt = f"""你是一名{subject}领域的资深教师。请为"{topic}"课程生成总结页内容。

课程主题：{topic}
目标受众：{audience}
本节课涉及的知识点：{', '.join(knowledge_topics)}
本课具体教学内容摘要（总结须与之对应）：{(teaching_content or '')[:1800]}

要求：
1. knowledge_review：与上面每个知识点逐一对应，用**完整陈述句**总结（每条 20-40 字），禁止空泛
2. goals_achievement：说明本课目标达成证据（结合上面的内容）
3. homework：分层布置**可检查的具体任务**（题目或任务描述），禁止只写「复习本章」

请严格以JSON格式输出，不要输出其他内容：
{{"knowledge_review": ["总结1", "总结2", ...], "goals_achievement": "目标完成情况", "homework": "课后作业内容"}}"""
        
        response = llm_service.chat(prompt, [])
        
        try:
            parsed = self._safe_parse_json(response)
            if parsed and isinstance(parsed, dict):
                parsed.update({
                    "page_num": page.get("page_num"),
                    "page_type": page.get("page_type"),
                    "core_topic": page.get("core_topic")
                })
                if "knowledge_review" not in parsed or not parsed["knowledge_review"]:
                    parsed["knowledge_review"] = knowledge_topics
                return parsed
        except Exception as e:
            print(f"解析总结页内容失败: {e}")
        
        return {
            "page_num": page.get("page_num"),
            "page_type": page.get("page_type"),
            "core_topic": page.get("core_topic"),
            "knowledge_review": knowledge_topics if knowledge_topics else [f"掌握了{topic}的核心概念", f"理解了{topic}的基本原理", f"了解了{topic}的应用场景"],
            "goals_achievement": f"通过本节课的学习，学生已掌握{topic}的核心知识，具备基本的分析和应用能力。",
            "homework": f"基础巩固：复习本节课内容，整理{topic}的知识要点\n能力提升：结合实际案例，分析{topic}在实践中的应用"
        }

    def _generate_extension_content(self, page: Dict, topic: str, audience: str, duration: int, subject: str, teaching_content: str = "") -> Dict:
        """生成拓展页内容"""
        prompt = f"""你是一名{subject}领域的资深教师。请为"{topic}"课程生成拓展资源页内容。

课程主题：{topic}
目标受众：{audience}
学科领域：{subject}

要求：
1. after_class_thoughts数组：3个课后思考题
2. reference_materials数组：3个推荐学习资源（书名+作者，或网站名称）
3. practice_projects数组：2个实践项目建议

请严格以JSON格式输出，不要输出其他内容。"""
        
        response = llm_service.chat(prompt, [])
        
        try:
            parsed = self._safe_parse_json(response)
            if parsed and isinstance(parsed, dict):
                parsed.update({
                    "page_num": page.get("page_num"),
                    "page_type": page.get("page_type"),
                    "core_topic": page.get("core_topic")
                })
                return parsed
        except Exception as e:
            print(f"解析拓展页内容失败: {e}")
        
        return {
            "page_num": page.get("page_num"),
            "page_type": page.get("page_type"),
            "core_topic": page.get("core_topic"),
            "after_class_thoughts": [f"{topic}在未来的发展趋势是什么？", f"如何将{topic}的知识应用到实际问题中？", f"{topic}与相关领域有哪些交叉和融合？"],
            "reference_materials": [f"《{topic}入门与实践》", f"《{subject}前沿进展》", f"相关领域在线学习平台资源"],
            "practice_projects": [f"基于{topic}的综合实践项目", f"{topic}知识的实际应用案例分析"],
            "notes": f"引导学生自主拓展{topic}的学习，培养终身学习能力。"
        }

    def _generate_default_content(self, page: Dict, topic: str, audience: str, duration: int, subject: str, teaching_content: str = "") -> Dict:
        """生成默认页面内容"""
        return {
            "page_num": page.get("page_num"),
            "page_type": page.get("page_type"),
            "core_topic": page.get("core_topic"),
            "key_points": page.get("content_outline", [f"{topic}的核心要点"]),
            "notes": "页面内容"
        }

    def _get_default_visual_style(self, theme_color: str, style_preference: str) -> Dict:
        """获取默认视觉风格"""
        color_schemes = {
            "蓝色系": {"primary": "#3498db", "secondary": "#2980b9", "text": "#2c3e50", "background": "#ffffff"},
            "绿色系": {"primary": "#2ecc71", "secondary": "#27ae60", "text": "#2c3e50", "background": "#ffffff"},
            "红色系": {"primary": "#e74c3c", "secondary": "#c0392b", "text": "#2c3e50", "background": "#ffffff"},
            "紫色系": {"primary": "#9b59b6", "secondary": "#8e44ad", "text": "#2c3e50", "background": "#ffffff"},
            "橙色系": {"primary": "#f39c12", "secondary": "#e67e22", "text": "#2c3e50", "background": "#ffffff"}
        }
        
        return {
            "color_scheme": color_schemes.get(theme_color, color_schemes["蓝色系"]),
            "font_specs": {"title": "微软雅黑", "body": "微软雅黑", "title_size": 36, "body_size": 20},
            "layout_style": {"margin": 1.0, "alignment": "left", "spacing": 1.5}
        }
