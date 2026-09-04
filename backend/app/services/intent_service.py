"""教学意图识别服务"""
import json
import re
from typing import Dict, List, Optional
from .llm_service import llm_service

class IntentService:
    """教学意图识别服务类"""
    
    def __init__(self):
        """初始化意图识别服务"""
        self.intent_templates = {
            "course_design": {
                "keywords": ["设计", "课程", "课件", "教案", "PPT", "教学设计", "备课"],
                "required_fields": ["topic", "target_audience", "duration", "key_points"],
                "followup_templates": [
                    "需要我帮您生成配套的PPT课件吗？",
                    "要不要我帮您设计课堂互动环节？",
                    "需要为这个课程生成教学动画吗？"
                ]
            },
            "knowledge_question": {
                "keywords": ["什么是", "如何", "为什么", "解释", "原理", "方法", "区别", "概念"],
                "required_fields": ["topic", "specific_question"],
                "followup_templates": [
                    "需要我进一步解释某个知识点吗？",
                    "要不要我帮您把这个知识点整理成教学内容？",
                    "需要生成关于这个主题的练习题吗？"
                ]
            },
            "resource_generation": {
                "keywords": ["生成", "创建", "制作", "开发", "做一个", "帮我做"],
                "required_fields": ["resource_type", "topic", "requirements"],
                "followup_templates": [
                    "需要调整生成内容的难度级别吗？",
                    "要不要我生成配套的教学资源？",
                    "需要我修改或完善生成的内容吗？"
                ]
            },
            "teaching_advice": {
                "keywords": ["建议", "意见", "方法", "策略", "技巧", "如何教", "怎么上课"],
                "required_fields": ["topic", "specific_issue"],
                "followup_templates": [
                    "需要针对具体学科给出更详细的建议吗？",
                    "要不要我帮您设计完整的教学方案？",
                    "需要参考其他优秀教师的教学案例吗？"
                ]
            }
        }
    
    def quick_intent_check(self, message: str) -> Optional[Dict]:
        """快速关键词预检 - 不调用LLM，毫秒级响应"""
        message_lower = message.lower()
        best_match = None
        best_score = 0
        
        for intent_type, template in self.intent_templates.items():
            score = sum(1 for kw in template["keywords"] if kw in message_lower)
            if score > best_score:
                best_score = score
                best_match = intent_type
        
        if best_score == 0:
            return None
        
        return {
            "intent_type": best_match,
            "confidence": min(0.3 + best_score * 0.15, 0.85),
            "method": "keyword"
        }

    def generate_followup_suggestions(self, message: str, response: str, intent_type: str = None) -> List[str]:
        """根据对话内容生成后续建议 - 快速模板匹配"""
        suggestions = []
        
        # 如果有明确意图类型，使用对应模板
        if intent_type and intent_type in self.intent_templates:
            suggestions = self.intent_templates[intent_type]["followup_templates"][:2]
        
        # 基于关键词的通用建议
        if "PPT" in message or "课件" in message:
            suggestions.append("需要我帮您优化PPT的内容结构吗？")
        if "教案" in message or "课程" in message:
            suggestions.append("需要我帮您生成配套的教案吗？")
        if any(kw in message for kw in ["动画", "视频", "演示"]):
            suggestions.append("需要我帮您生成教学动画吗？")
        if any(kw in message for kw in ["游戏", "互动", "活动"]):
            suggestions.append("需要我帮您设计互动游戏环节吗？")
        
        # 通用建议（总是加一条）
        if not suggestions:
            suggestions = ["需要我帮您把这些内容整理成教学资料吗？", "需要进一步了解相关知识点吗？"]
        
        # 去重并限制数量
        seen = set()
        unique = []
        for s in suggestions:
            if s not in seen:
                seen.add(s)
                unique.append(s)
        return unique[:3]

    def analyze_intent(self, message: str, history: List[Dict] = None) -> Dict:
        """分析用户意图
        
        Args:
            message: 用户消息
            history: 对话历史
            
        Returns:
            包含意图分析结果的字典
        """
        if history is None:
            history = []
        
        # 先尝试快速关键词匹配
        quick_result = self.quick_intent_check(message)
        if quick_result and quick_result["confidence"] >= 0.6:
            intent_type = quick_result["intent_type"]
            template = self.intent_templates[intent_type]
            return {
                "intent_type": intent_type,
                "confidence": quick_result["confidence"],
                "extracted_fields": {},
                "missing_fields": template["required_fields"],
                "clarification_questions": self.generate_clarification(intent_type, template["required_fields"]),
                "followup_suggestions": self.generate_followup_suggestions(message, "", intent_type)
            }
        
        # 构建提示词
        history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history[-6:]])
        prompt = f"""请分析以下教学相关的用户消息，识别其意图类型，并提取相关的教学要素：
        
消息：{message}

对话历史：
{history_str}

意图类型包括：
1. course_design: 课程设计/课件制作
2. knowledge_question: 知识问题咨询
3. resource_generation: 教学资源生成
4. teaching_advice: 教学建议请求

请返回JSON格式，包含：
- intent_type: 意图类型
- confidence: 置信度 (0-1)
- extracted_fields: 提取的字段
- missing_fields: 缺失的必填字段
- clarification_questions: 需要澄清的问题（如果有）"""
        
        # 调用LLM进行意图分析
        response = llm_service.chat(prompt, [], "")
        
        # 解析LLM响应
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = json.loads(response)
            
            # 补充followup_suggestions
            intent_type = result.get("intent_type", "knowledge_question")
            result["followup_suggestions"] = self.generate_followup_suggestions(
                message, "", intent_type
            )
            return result
        except Exception:
            # 如果解析失败，返回默认结果
            intent_type = quick_result["intent_type"] if quick_result else "knowledge_question"
            return {
                "intent_type": intent_type,
                "confidence": 0.5,
                "extracted_fields": {},
                "missing_fields": self.intent_templates.get(intent_type, {}).get("required_fields", []),
                "clarification_questions": ["请问您想了解什么内容？"],
                "followup_suggestions": self.generate_followup_suggestions(message, "", intent_type)
            }
    
    def generate_clarification(self, intent_type: str, missing_fields: List[str]) -> List[str]:
        """生成澄清问题"""
        clarification_map = {
            "course_design": {
                "topic": "请问您想设计什么主题的课程？",
                "target_audience": "目标学生群体是哪些？",
                "duration": "课时时长是多少？",
                "key_points": "核心知识点有哪些？"
            },
            "knowledge_question": {
                "topic": "请问您想了解什么主题的知识？",
                "specific_question": "具体的问题是什么？"
            },
            "resource_generation": {
                "resource_type": "您想生成什么类型的教学资源？",
                "topic": "资源的主题是什么？",
                "requirements": "有什么具体要求？"
            },
            "teaching_advice": {
                "topic": "您想获得哪方面的教学建议？",
                "specific_issue": "具体的问题是什么？"
            }
        }
        
        questions = []
        if intent_type in clarification_map:
            for field in missing_fields:
                if field in clarification_map[intent_type]:
                    questions.append(clarification_map[intent_type][field])
        
        return questions
    
    def validate_intent(self, intent_data: Dict) -> bool:
        """验证意图数据是否完整"""
        intent_type = intent_data.get("intent_type")
        extracted_fields = intent_data.get("extracted_fields", {})
        
        if intent_type in self.intent_templates:
            required_fields = self.intent_templates[intent_type]["required_fields"]
            for field in required_fields:
                if field not in extracted_fields or not extracted_fields[field]:
                    return False
        
        return True

# 实例化意图识别服务
intent_service = IntentService()