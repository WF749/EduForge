"""LLM服务"""
from typing import List, Optional, Dict
from .llm.service import llm_service as new_llm_service

class LLMServices:
    """LLM服务类"""
    
    def __init__(self):
        """初始化LLM服务"""
        # 确保new_llm_service被初始化
        global new_llm_service
        # 访问new_llm_service的一个属性，触发其初始化
        _ = new_llm_service.providers
    
    def set_provider(self, provider: str):
        """设置LLM提供商"""
        # 设置激活的LLM提供商
        self.set_active_provider(provider)
    
    def chat(
        self,
        message: str,
        history: List[Dict] = None,
        knowledge: str = "",
        provider: Optional[str] = None,
        purpose: str = "chat",
        stage: str = "",
    ):
        """与LLM对话。

        `purpose` / `stage` 说明本次调用的**任务用途与执行阶段**，供采样策略
        自动选择温度（见 `core.sampling`）。生成类调用应当传入，例如：
          - 教案 / 课件正文 → `lesson_plan_content` / `courseware_content`
          - 课堂活动、游戏玩法构思 → `activity_design` / `gameplay_ideation`
          - 动画 / 游戏**代码**生成 → `animation_code` / `game_code`
        """
        if history is None:
            history = []

        # 调用新的统一LLM服务
        prompt = message
        if knowledge:
            prompt = f"{message}\n\n{knowledge}"
        return new_llm_service.chat_completions(
            prompt, history, provider=provider, purpose=purpose, stage=stage)
    
    def stream_chat(self, message: str, history: List[Dict] = None, knowledge: str = "", provider: Optional[str] = None, purpose: str = "chat", stage: str = ""):
        """流式与LLM对话"""
        if history is None:
            history = []
        
        # 构建完整的提示
        prompt = message
        if knowledge:
            prompt = f"{message}\n\n{knowledge}"
        
        # 调用新的统一LLM服务
        for chunk in new_llm_service.stream_chat_completions(
            prompt=prompt,
            history=history,
            provider=provider,
            api_key=None,
            base_url=None,
            temperature=None,
            model=None,
            purpose=purpose,
            stage=stage
        ):
            yield chunk
    
    def deep_thinking(self, message: str, history: List[Dict] = None, knowledge: str = ""):
        """深度思考功能"""
        if history is None:
            history = []
        
        # 构建思考提示
        history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history])
        thinking_prompt = f"""请对以下问题进行深度思考，分析问题的各个方面，然后给出详细的思考过程和最终回答：

问题：{message}

历史对话：
{history_str}

{knowledge}

请按照以下格式输出：

## 思考过程
1. 问题分析：详细分析用户的问题需求和背景，识别问题的核心要素
2. 知识关联：联系相关的教学理论、研究成果和实践经验
3. 多角度思考：从不同角度分析问题，考虑可能的解决方案
4. 方案评估：评估各种解决方案的优缺点和可行性
5. 实施建议：提供详细的实施步骤、注意事项和预期效果

## 最终回答
- 内容要专业、结构清晰、逻辑严密
- 使用层次分明的结构，如标题、列表、编号等
- 语言要简洁明了，避免冗长和重复
- 提供具体的实施建议和示例，增强实用性
- 保持客观中立的专业态度，基于事实和证据
- 考虑不同情境下的适用性，提供灵活的解决方案
- 包含可量化的目标和评估标准，便于跟踪实施效果"""
        
        # 调用新的统一LLM服务
        try:
            result = new_llm_service.chat_completions(thinking_prompt, history)
            return result
        except Exception as e:
            # 兜底到演示模式
            return f'基于你的问题，我生成了以下内容：\n\n# 思考过程\n1. 问题分析：详细分析了你的问题需求和背景\n2. 知识关联：联系了相关的教学理论和实践经验\n3. 多角度思考：从不同角度分析了问题\n4. 方案评估：评估了各种解决方案的优缺点\n5. 实施建议：提供了详细的实施步骤和注意事项\n\n# 最终回答\n根据你的需求，我为你提供了详细的解决方案。这是一个示例响应，实际使用时会调用真实的AI模型生成更详细、更专业的内容。'
    
    def stream_deep_thinking(self, message: str, history: List[Dict] = None, knowledge: str = "", provider: Optional[str] = None):
        """流式深度思考功能"""
        if history is None:
            history = []
        
        # 构建思考提示
        history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history])
        thinking_prompt = f"""请对以下问题进行深度思考，分析问题的各个方面，然后给出详细的思考过程和最终回答：

问题：{message}

历史对话：
{history_str}

{knowledge}

请按照以下格式输出：

## 思考过程
1. 问题分析：详细分析用户的问题需求和背景，识别问题的核心要素
2. 知识关联：联系相关的教学理论、研究成果和实践经验
3. 多角度思考：从不同角度分析问题，考虑可能的解决方案
4. 方案评估：评估各种解决方案的优缺点和可行性
5. 实施建议：提供详细的实施步骤、注意事项和预期效果

## 最终回答
- 内容要专业、结构清晰、逻辑严密
- 使用层次分明的结构，如标题、列表、编号等
- 语言要简洁明了，避免冗长和重复
- 提供具体的实施建议和示例，增强实用性
- 保持客观中立的专业态度，基于事实和证据
- 考虑不同情境下的适用性，提供灵活的解决方案
- 包含可量化的目标和评估标准，便于跟踪实施效果"""
        
        # 调用新的统一LLM服务
        for chunk in new_llm_service.stream_chat_completions(
            prompt=thinking_prompt, 
            history=history, 
            provider=provider, 
            api_key=None, 
            base_url=None, 
            temperature=None, 
            model=None
        ):
            yield chunk
    
    def get_all_configs(self):
        """获取所有配置"""
        return new_llm_service.get_all_configs()
    
    def get_active_provider(self):
        """获取当前激活的提供商"""
        return new_llm_service.get_active_provider()
    
    def save_config(self, provider, api_key, base_url, model, temperature, is_active=False):
        """保存配置"""
        return new_llm_service.save_config(provider, api_key, base_url, model, temperature, is_active)
    
    def get_config(self, provider):
        """获取配置"""
        return new_llm_service.get_config(provider)
    
    def test_connection(self, provider, api_key, base_url):
        """测试连接"""
        return new_llm_service.test_connection(provider, api_key, base_url)
    
    def list_models(self, provider, api_key, base_url):
        """获取模型列表"""
        return new_llm_service.list_models(provider, api_key, base_url)
    
    def set_active_provider(self, provider):
        """设置激活提供商"""
        return new_llm_service.set_active_provider(provider)
    
    def get_last_db_error(self):
        """获取最近一次数据库错误信息"""
        return new_llm_service.get_last_db_error()

# 实例化LLM服务
llm_service = LLMServices()