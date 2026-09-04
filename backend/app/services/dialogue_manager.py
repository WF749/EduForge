"""对话管理服务 - 处理多轮对话、追问确认、复杂意图理解"""
import re
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .llm_service import llm_service
from .intent_service import intent_service


class DialogueState(Enum):
    """对话状态枚举"""
    INITIAL = "initial"           # 初始状态
    CLARIFYING = "clarifying"     # 澄清/追问中
    CONFIRMING = "confirming"     # 确认中
    EXECUTING = "executing"       # 执行中
    COMPLETED = "completed"       # 已完成


@dataclass
class DialogueTurn:
    """对话轮次数据"""
    role: str
    content: str
    timestamp: float = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DialogueContext:
    """对话上下文"""
    conversation_id: str
    state: DialogueState = DialogueState.INITIAL
    current_intent: Optional[str] = None
    intent_confidence: float = 0.0
    extracted_fields: Dict[str, Any] = field(default_factory=dict)
    missing_fields: List[str] = field(default_factory=list)
    clarification_history: List[str] = field(default_factory=list)
    turns: List[DialogueTurn] = field(default_factory=list)
    last_action: Optional[str] = None
    user_preferences: Dict[str, Any] = field(default_factory=dict)


class DialogueManager:
    """对话管理器 - 处理多轮对话状态和追问确认"""
    
    def __init__(self):
        self.contexts: Dict[str, DialogueContext] = {}
        # 追问策略配置
        self.clarification_strategies = {
            "course_design": {
                "priority_order": ["topic", "target_audience", "duration", "key_points"],
                "max_questions": 3,  # 最多追问3个问题
                "combine_questions": True  # 是否合并多个问题
            },
            "knowledge_question": {
                "priority_order": ["topic", "specific_question"],
                "max_questions": 2,
                "combine_questions": True
            },
            "resource_generation": {
                "priority_order": ["resource_type", "topic", "requirements"],
                "max_questions": 3,
                "combine_questions": True
            },
            "teaching_advice": {
                "priority_order": ["topic", "specific_issue"],
                "max_questions": 2,
                "combine_questions": True
            }
        }
        
        # 确认提示模板
        self.confirmation_templates = {
            "course_design": (
                "根据您的需求，我理解为：\n"
                "- 主题：{topic}\n"
                "- 受众：{target_audience}\n"
                "- 时长：{duration}分钟\n"
                "- 要点：{key_points}\n\n"
                "请问理解正确吗？"
            ),
            "resource_generation": (
                "我将为您生成：\n"
                "- 类型：{resource_type}\n"
                "- 主题：{topic}\n"
                "- 要求：{requirements}\n\n"
                "确认开始生成吗？"
            )
        }
    
    def get_or_create_context(self, conversation_id: str) -> DialogueContext:
        """获取或创建对话上下文"""
        if conversation_id not in self.contexts:
            self.contexts[conversation_id] = DialogueContext(
                conversation_id=conversation_id
            )
        return self.contexts[conversation_id]
    
    def add_turn(self, context: DialogueContext, role: str, content: str, **metadata):
        """添加对话轮次"""
        import time
        turn = DialogueTurn(
            role=role,
            content=content,
            timestamp=time.time(),
            metadata=metadata
        )
        context.turns.append(turn)
    
    def analyze_and_update(self, conversation_id: str, user_message: str) -> Dict[str, Any]:
        """分析用户消息并更新对话状态
        
        Returns:
            包含对话状态、需要追问的问题、或需要执行的操作
        """
        context = self.get_or_create_context(conversation_id)
        self.add_turn(context, "user", user_message)
        
        # 根据当前状态进行不同处理
        if context.state == DialogueState.INITIAL:
            return self._handle_initial_state(context, user_message)
        elif context.state == DialogueState.CLARIFYING:
            return self._handle_clarifying_state(context, user_message)
        elif context.state == DialogueState.CONFIRMING:
            return self._handle_confirming_state(context, user_message)
        else:
            return self._handle_default_state(context, user_message)
    
    def _handle_initial_state(self, context: DialogueContext, message: str) -> Dict[str, Any]:
        """处理初始状态 - 进行意图识别"""
        # 分析意图
        history = [{"role": t.role, "content": t.content} for t in context.turns[-10:]]
        intent_result = intent_service.analyze_intent(message, history)
        
        context.current_intent = intent_result.get("intent_type", "knowledge_question")
        context.intent_confidence = intent_result.get("confidence", 0.5)
        context.extracted_fields = intent_result.get("extracted_fields", {})
        context.missing_fields = intent_result.get("missing_fields", [])
        
        # 如果置信度很高且字段完整，直接进入确认状态
        if (context.intent_confidence >= 0.85 and 
            not context.missing_fields and 
            context.current_intent in self.confirmation_templates):
            context.state = DialogueState.CONFIRMING
            return {
                "action": "confirm",
                "intent_type": context.current_intent,
                "confidence": context.intent_confidence,
                "message": self._generate_confirmation_message(context),
                "extracted_fields": context.extracted_fields
            }
        
        # 如果有缺失字段，进入澄清状态
        if context.missing_fields:
            context.state = DialogueState.CLARIFYING
            clarification = self._generate_clarification_message(context)
            return {
                "action": "clarify",
                "intent_type": context.current_intent,
                "confidence": context.intent_confidence,
                "message": clarification,
                "missing_fields": context.missing_fields
            }
        
        # 否则直接执行
        context.state = DialogueState.EXECUTING
        return {
            "action": "execute",
            "intent_type": context.current_intent,
            "confidence": context.intent_confidence,
            "extracted_fields": context.extracted_fields,
            "followup_suggestions": intent_service.generate_followup_suggestions(
                message, "", context.current_intent
            )
        }
    
    def _handle_clarifying_state(self, context: DialogueContext, message: str) -> Dict[str, Any]:
        """处理澄清状态 - 解析用户对追问的回答"""
        # 从用户回答中提取信息补充到extracted_fields
        updated_fields = self._extract_info_from_response(
            message, context.current_intent, context.missing_fields
        )
        context.extracted_fields.update(updated_fields)
        
        # 更新缺失字段列表
        still_missing = [
            f for f in context.missing_fields 
            if f not in context.extracted_fields or not context.extracted_fields[f]
        ]
        context.missing_fields = still_missing
        
        # 如果还有缺失字段，继续追问
        if still_missing:
            clarification = self._generate_clarification_message(context)
            return {
                "action": "clarify",
                "intent_type": context.current_intent,
                "message": clarification,
                "missing_fields": still_missing
            }
        
        # 如果信息完整且需要确认，进入确认状态
        if context.current_intent in self.confirmation_templates:
            context.state = DialogueState.CONFIRMING
            return {
                "action": "confirm",
                "intent_type": context.current_intent,
                "message": self._generate_confirmation_message(context),
                "extracted_fields": context.extracted_fields
            }
        
        # 否则执行
        context.state = DialogueState.EXECUTING
        return {
            "action": "execute",
            "intent_type": context.current_intent,
            "extracted_fields": context.extracted_fields
        }
    
    def _handle_confirming_state(self, context: DialogueContext, message: str) -> Dict[str, Any]:
        """处理确认状态 - 解析用户的确认/取消"""
        # 判断用户是确认还是取消
        confirmation = self._parse_confirmation(message)
        
        if confirmation is True:
            # 用户确认，执行操作
            context.state = DialogueState.EXECUTING
            return {
                "action": "execute",
                "intent_type": context.current_intent,
                "extracted_fields": context.extracted_fields,
                "confirmed": True
            }
        elif confirmation is False:
            # 用户取消，重置状态
            context.state = DialogueState.INITIAL
            context.extracted_fields = {}
            context.missing_fields = []
            return {
                "action": "reset",
                "message": "好的，我理解有误。请重新描述您的需求。",
                "intent_type": None
            }
        else:
            # 不确定，再次询问
            return {
                "action": "confirm",
                "intent_type": context.current_intent,
                "message": "请问您是确认吗？（是的/确认/对 或者 不是/取消/不对）",
                "extracted_fields": context.extracted_fields
            }
    
    def _handle_default_state(self, context: DialogueContext, message: str) -> Dict[str, Any]:
        """处理默认状态 - 重置为初始状态重新分析"""
        context.state = DialogueState.INITIAL
        return self._handle_initial_state(context, message)
    
    def _generate_clarification_message(self, context: DialogueContext) -> str:
        """生成追问消息"""
        strategy = self.clarification_strategies.get(
            context.current_intent, 
            {"priority_order": context.missing_fields, "max_questions": 3, "combine_questions": True}
        )
        
        # 按优先级排序缺失字段
        priority_order = strategy.get("priority_order", context.missing_fields)
        sorted_missing = [f for f in priority_order if f in context.missing_fields]
        
        # 限制追问数量
        max_q = strategy.get("max_questions", 3)
        fields_to_ask = sorted_missing[:max_q]
        
        # 生成问题
        questions = intent_service.generate_clarification(
            context.current_intent, fields_to_ask
        )
        
        if strategy.get("combine_questions", True) and len(questions) > 1:
            # 合并多个问题
            combined = "为了更好地帮您，我需要确认几个信息：\n"
            combined += "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
            return combined
        
        return questions[0] if questions else "请提供更多信息。"
    
    def _generate_confirmation_message(self, context: DialogueContext) -> str:
        """生成确认消息"""
        template = self.confirmation_templates.get(context.current_intent)
        if not template:
            fields_str = ", ".join([f"{k}={v}" for k, v in context.extracted_fields.items()])
            return f"确认信息：{fields_str}？"
        
        # 填充模板
        try:
            return template.format(**context.extracted_fields)
        except KeyError:
            # 模板字段不匹配，使用默认格式
            fields_str = "\n".join([f"- {k}: {v}" for k, v in context.extracted_fields.items()])
            return f"确认信息：\n{fields_str}\n\n请问理解正确吗？"
    
    def _extract_info_from_response(self, message: str, intent_type: str, 
                                    missing_fields: List[str]) -> Dict[str, str]:
        """从用户回答中提取缺失的信息"""
        extracted = {}
        
        # 简单的关键词提取逻辑
        message_lower = message.lower()
        
        # 针对不同字段的提取规则
        field_patterns = {
            "topic": ["主题", "题目", "关于", "讲", "教", "课程"],
            "target_audience": ["学生", "年级", "受众", "对象", "面向"],
            "duration": ["分钟", "课时", "时长", "时间"],
            "key_points": ["要点", "重点", "内容", "知识点"],
            "resource_type": ["PPT", "课件", "教案", "动画", "游戏", "类型"],
            "requirements": ["要求", "需要", "希望", "想要"],
            "specific_question": ["问题是", "具体是", "想知道", "想了解"]
        }
        
        for field in missing_fields:
            patterns = field_patterns.get(field, [])
            for pattern in patterns:
                if pattern in message:
                    # 简单提取冒号或后面的内容
                    for sep in ["：", ":", "是", "为"]:
                        if sep in message and message.index(sep) > message.index(pattern):
                            idx = message.index(sep) + 1
                            value = message[idx:].strip().split("\n")[0].split("，")[0].split("。")[0]
                            if value and len(value) > 1:
                                extracted[field] = value
                                break
                    break
            
            # 如果没找到但消息较短，可能直接就是答案
            if field not in extracted and len(message) < 100 and not any(c in message for c in ["？", "?", "我想"]):
                extracted[field] = message
        
        return extracted
    
    def _parse_confirmation(self, message: str) -> Optional[bool]:
        """解析用户的确认回答
        
        Returns:
            True: 确认
            False: 取消/否定
            None: 不确定
        """
        message = message.strip().lower()
        
        # 肯定词
        positive_words = ["是", "对", "好", "确认", "没错", "正确", "是的", "可以", "行", "嗯"]
        # 否定词
        negative_words = ["不", "不对", "不是", "错了", "取消", "不行", "不要", "重新", "改"]
        
        has_positive = any(w in message for w in positive_words)
        has_negative = any(w in message for w in negative_words)
        
        # 如果同时有肯定和否定，需要看哪个更明确
        if has_positive and has_negative:
            # 检查是否是"不是不对"这种双重否定
            if "不是不对" in message or "不是不可以" in message:
                return True
            # 检查否定是否在前面
            for neg in negative_words:
                for pos in positive_words:
                    if neg in message and pos in message:
                        if message.index(neg) < message.index(pos):
                            return False
            return None
        
        if has_positive:
            return True
        if has_negative:
            return False
        
        return None
    
    def reset_context(self, conversation_id: str):
        """重置对话上下文"""
        if conversation_id in self.contexts:
            del self.contexts[conversation_id]


# 全局对话管理器实例
dialogue_manager = DialogueManager()
