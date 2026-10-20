"""演示模式LLM实现 - 根据实际主题动态生成内容"""
import json
import re
from typing import List, Dict, Optional, Any, Generator
from .base import LLMProviderBase

# 设计思路参考了社区开源的教学设计实现，核心代码为本项目自主编写

class DemoProvider(LLMProviderBase):
    """演示模式LLM提供商 - 根据主题动态生成结构化内容"""
    
    def test_connection(self, api_key: str, base_url: Optional[str] = None) -> Dict[str, Any]:
        """测试连接与密钥有效性"""
        return {'success': True, 'message': '演示模式连接成功'}
    
    def list_models(self, api_key: str, base_url: Optional[str] = None) -> List[Dict[str, str]]:
        """获取可用模型列表"""
        return [{'name': 'demo-model', 'description': '演示模型'}]

    def _extract_topic_from_prompt(self, prompt: str) -> str:
        """从prompt中提取课程主题"""
        # 尝试多种模式提取主题
        patterns = [
            r"课程主题[：:][\s]*([^\n]+)",
            r"主题为['\"]?([^'\"，\n]+)",
            r"关于['\"]?([^'\"，\n的]+)['\"]?的",
            r'"{1}([^"]{2,30})"{1}课程',
        ]
        for pat in patterns:
            m = re.search(pat, prompt)
            if m:
                return m.group(1).strip().strip("'\"")
        return "课程内容"

    def _extract_audience_from_prompt(self, prompt: str) -> str:
        """从prompt中提取目标受众"""
        patterns = [
            r"目标受众[：:][\s]*([^\n]+)",
            r"面向[\s]*([^\n，。的]+)",
        ]
        for pat in patterns:
            m = re.search(pat, prompt)
            if m:
                return m.group(1).strip()
        return "学生"

    def _extract_subject_from_prompt(self, prompt: str) -> str:
        """从prompt中提取学科领域"""
        patterns = [
            r"学科领域[：:][\s]*([^\n]+)",
            r"的([^\n]{2,8})课程",
        ]
        for pat in patterns:
            m = re.search(pat, prompt)
            if m:
                val = m.group(1).strip()
                if val and val != "general":
                    return val
        return "通用"

    def chat_completions(
        self,
        prompt: str,
        history: List[Dict],
        temperature: float = 0.7,
        api_key: str = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> str:
        """统一的对话生成方法 - 根据prompt类型返回对应的JSON结构"""
        
        topic = self._extract_topic_from_prompt(prompt)
        audience = self._extract_audience_from_prompt(prompt)
        subject = self._extract_subject_from_prompt(prompt)

        # ===== PPT大纲生成 =====
        if any(kw in prompt for kw in ['PPT大纲', 'page_num', 'page_type', 'PPT课件生成一页']):
            return self._generate_outline(topic, audience, prompt)

        # ===== 教学目标生成 =====
        if any(kw in prompt for kw in ['教学目标', 'knowledge_goals', 'ability_goals', 'emotional_goals']):
            return self._generate_goals(topic, audience, subject)

        # ===== 封面页内容 =====
        if any(kw in prompt for kw in ['封面页', 'main_title', '副标题']):
            return self._generate_cover(topic, audience, subject)

        # ===== 目录页内容 =====
        if 'toc_items' in prompt or '目录页' in prompt:
            return self._generate_toc(topic)

        # ===== 知识点页内容 =====
        if any(kw in prompt for kw in ['key_points', '知识点要点', '详细教学内容', '详细PPT页面内容']):
            core = self._extract_core_topic(prompt)
            return self._generate_knowledge(topic, audience, core)

        # ===== 互动练习 =====
        if any(kw in prompt for kw in ['exercises', '互动练习', '练习题', '课堂互动']):
            return self._generate_exercises(topic, audience)

        # ===== 总结页 =====
        if any(kw in prompt for kw in ['knowledge_review', '总结页', '课程总结']):
            return self._generate_summary(topic, audience)

        # ===== 拓展页 =====
        if any(kw in prompt for kw in ['after_class_thoughts', '拓展资源', 'reference_materials', '拓展']):
            return self._generate_extension(topic, audience, subject)

        # ===== 通用回复 =====
        return self._generate_default_response(prompt, topic)

    def _extract_core_topic(self, prompt: str) -> str:
        """从prompt中提取当前页面的核心主题"""
        patterns = [
            r"当前页面主题[：:][\s]*([^\n]+)",
            r"关于['\"]([^'\"]+)['\"]的",
            r"核心知识点标题['\"]([^'\"]+)",
        ]
        for pat in patterns:
            m = re.search(pat, prompt)
            if m:
                return m.group(1).strip()
        return "核心知识点"

    # ===== 各类内容生成方法 =====

    def _generate_outline(self, topic: str, audience: str, prompt: str) -> str:
        """生成PPT大纲"""
        # 尝试提取课时信息
        duration = 45
        m = re.search(r'课时时长[：:]?\s*(\d+)', prompt)
        if m:
            duration = int(m.group(1))

        # 基本结构
        pages = [
            {"page_num": 1, "page_type": "cover", "core_topic": "课程封面", "content_outline": [topic, f"面向{audience}", "课程介绍", "授课信息"]},
            {"page_num": 2, "page_type": "toc", "core_topic": "课程目录", "content_outline": ["课程导入", f"{topic}概述", f"{topic}核心原理", f"{topic}实践应用", "互动练习", "课程总结"]},
            {"page_num": 3, "page_type": "knowledge", "core_topic": f"{topic} - 基础概念", "content_outline": [f"{topic}的定义与内涵", f"{topic}的发展历程", f"{topic}的核心特征", f"{topic}的应用领域"]},
            {"page_num": 4, "page_type": "knowledge", "core_topic": f"{topic} - 核心原理", "content_outline": [f"{topic}的基本原理", f"{topic}的关键要素", f"{topic}的运作机制", f"{topic}的核心框架"]},
            {"page_num": 5, "page_type": "knowledge", "core_topic": f"{topic} - 实践应用", "content_outline": [f"{topic}的应用场景", f"{topic}的操作方法", f"{topic}的最佳实践", f"{topic}的常见问题"]},
        ]

        if duration >= 45:
            pages.append({"page_num": 6, "page_type": "knowledge", "core_topic": f"{topic} - 案例分析", "content_outline": ["典型案例介绍", "案例详细解读", "经验与启示", "举一反三"]})
        if duration >= 60:
            pages.append({"page_num": 7, "page_type": "knowledge", "core_topic": f"{topic} - 进阶拓展", "content_outline": ["进阶知识要点", "行业发展趋势", "前沿研究动态", "未来展望"]})

        n = len(pages)
        pages.append({"page_num": n + 1, "page_type": "exercise", "core_topic": "课堂互动练习", "content_outline": ["知识巩固题", "思考讨论题", "实践操作题"]})
        pages.append({"page_num": n + 2, "page_type": "summary", "core_topic": "课程总结与回顾", "content_outline": ["核心要点复盘", "学习目标检验", "课后作业布置", "后续学习建议"]})

        if duration >= 45:
            pages.append({"page_num": n + 3, "page_type": "extension", "core_topic": "拓展资源与延伸", "content_outline": ["推荐阅读", "在线资源", "实践项目"]})

        return json.dumps(pages, ensure_ascii=False)

    def _generate_goals(self, topic: str, audience: str, subject: str) -> str:
        """生成教学目标"""
        return json.dumps({
            "knowledge_goals": [
                f"理解{topic}的核心概念和基本原理",
                f"掌握{topic}的关键知识点和重要特征",
                f"了解{topic}在{subject}领域的应用场景"
            ],
            "ability_goals": [
                f"能够运用{topic}的知识分析和解决实际问题",
                f"具备{topic}相关的实践操作和应用能力"
            ],
            "emotional_goals": [
                f"培养对{topic}领域的学习兴趣和探索精神",
                f"建立严谨求实的学习态度和创新意识"
            ]
        }, ensure_ascii=False)

    def _generate_cover(self, topic: str, audience: str, subject: str) -> str:
        """生成封面页内容"""
        return json.dumps({
            "main_title": topic,
            "subtitle": f"面向{audience}的{subject}课程",
            "instructor_info": "授课教师",
            "notes": f"欢迎{audience}参加{topic}课程学习"
        }, ensure_ascii=False)

    def _generate_toc(self, topic: str) -> str:
        """生成目录页内容"""
        return json.dumps({
            "toc_items": [
                f"{topic} - 基础概念",
                f"{topic} - 核心原理",
                f"{topic} - 实践应用",
                "课堂互动练习",
                "课程总结与回顾"
            ],
            "notes": "课程目录概览"
        }, ensure_ascii=False)

    def _generate_knowledge(self, topic: str, audience: str, core_topic: str) -> str:
        """生成知识点页内容"""
        return json.dumps({
            "key_points": [
                f"{core_topic}是{topic}的重要组成部分，具有基础性和关键性",
                f"深入理解{core_topic}需要掌握其核心概念、基本原理和应用方法",
                f"{core_topic}在实际场景中有着广泛的应用，是{audience}必须掌握的知识",
                f"学习{core_topic}需要注意理论与实践的结合，避免脱离实际",
                f"通过案例分析和动手实践，可以更好地理解和掌握{core_topic}"
            ],
            "case_study": f"在实际{topic}应用中，{core_topic}发挥着至关重要的作用。以一个典型场景为例：通过合理运用{core_topic}的核心知识，可以有效解决实际问题，提升工作效率和成果质量。这个案例充分说明了{core_topic}理论与实践结合的重要性。",
            "notes": f"重点讲解{core_topic}的核心概念和实际应用，结合案例帮助{audience}理解。注意根据{audience}的认知水平调整讲解深度。"
        }, ensure_ascii=False)

    def _generate_exercises(self, topic: str, audience: str) -> str:
        """生成互动练习"""
        return json.dumps({
            "exercises": [
                {
                    "question": f"关于{topic}的核心概念，以下哪项描述最准确？",
                    "options": [
                        f"A. {topic}的基本定义和核心特征的准确描述",
                        f"B. 对{topic}概念的片面理解",
                        f"C. 混淆了{topic}与相关概念的区别",
                        f"D. 对{topic}应用场景的错误判断"
                    ],
                    "answer": f"A. {topic}的基本定义和核心特征的准确描述"
                },
                {
                    "question": f"在实际应用中，{topic}最关键的要素是什么？",
                    "options": [
                        "A. 理论基础扎实",
                        "B. 实践经验丰富",
                        "C. 理论与实践相结合",
                        "D. 只需了解概念即可"
                    ],
                    "answer": "C. 理论与实践相结合"
                },
                {
                    "question": f"请结合所学知识，简述{topic}的核心要点及其实际应用价值。",
                    "answer": f"应从{topic}的概念、原理、特征、应用场景等方面进行阐述，结合实际案例说明其应用价值。"
                }
            ],
            "notes": f"通过练习巩固{topic}核心知识，鼓励{audience}积极参与讨论和互动。"
        }, ensure_ascii=False)

    def _generate_summary(self, topic: str, audience: str) -> str:
        """生成总结页"""
        return json.dumps({
            "knowledge_review": [
                f"掌握了{topic}的核心概念和基本定义",
                f"理解了{topic}的基本原理和关键要素",
                f"了解了{topic}的实际应用场景和操作方法",
                f"通过案例分析加深了对{topic}的理解"
            ],
            "goals_achievement": f"通过本节课的系统学习，{audience}已掌握{topic}的核心知识体系，具备了基本的分析和应用能力，达成了预设的学习目标。",
            "homework": f"基础巩固：复习本节课内容，整理{topic}的知识要点和思维导图\n能力提升：结合实际案例，分析{topic}在具体场景中的应用，撰写学习心得"
        }, ensure_ascii=False)

    def _generate_extension(self, topic: str, audience: str, subject: str) -> str:
        """生成拓展页"""
        return json.dumps({
            "after_class_thoughts": [
                f"{topic}在未来的发展趋势和前沿方向是什么？",
                f"如何将{topic}的知识创造性地应用到新的场景中？",
                f"{topic}与{subject}领域其他知识有哪些交叉和融合？"
            ],
            "reference_materials": [
                f"《{topic}入门与实践指南》",
                f"《{subject}领域前沿进展》",
                f"相关在线学习平台和MOOC课程资源"
            ],
            "practice_projects": [
                f"基于{topic}的综合实践项目设计与实施",
                f"{topic}知识在实际问题中的应用案例分析"
            ],
            "notes": f"引导{audience}自主拓展{topic}的学习，培养终身学习和自主探索的能力。"
        }, ensure_ascii=False)

    def _generate_default_response(self, prompt: str, topic: str) -> str:
        """通用默认回复"""
        # 简单的关键词匹配
        if '你好' in prompt:
            return '你好！我是 EduForge（演示模式）。演示内容由模板生成，并非真实模型输出；请配置 API Key 后体验真实生成。'
        if '如何使用' in prompt:
            return '你可以通过以下步骤使用系统：\n1. 在设置页面配置AI大模型\n2. 在课件生成中心创建教学课件\n3. 在知识库页面上传和管理文档\n4. 在智能对话页面与AI交流'
        if '深度思考' in prompt:
            return f'基于你的问题，我从多个角度进行了分析：\n\n## 思考过程\n1. 问题分析：识别了核心需求\n2. 知识关联：联系了相关理论和实践\n3. 方案设计：制定了可行的解决方案\n\n## 最终回答\n根据分析，建议采用系统化的方法来解决问题。'

        return f'感谢您的提问！我可以为您提供关于{topic}的教学辅助服务，包括课件设计、教案生成、知识库管理等。请告诉我您的具体需求。'

    def get_embeddings(
        self,
        text: str,
        api_key: str = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> List[float]:
        """获取文本嵌入向量"""
        return [0.0] * 768
    
    def stream_chat_completions(
        self,
        prompt: str,
        history: List[Dict],
        temperature: float = 0.7,
        api_key: str = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Generator[str, None, None]:
        """流式对话生成方法"""
        response = self.chat_completions(prompt, history, temperature, api_key, base_url, model)
        # 模拟流式输出
        chunk_size = max(10, len(response) // 20)
        for i in range(0, len(response), chunk_size):
            yield response[i:i+chunk_size]
