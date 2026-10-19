"""阿里云百炼（通义千问）LLM实现"""
from typing import List, Dict, Optional, Any, Generator
from .base import LLMProviderBase, sampling_kwargs

try:
    import dashscope
    from dashscope import MultiModalConversation
    HAS_DASHSCOPE = True
except ImportError:
    dashscope = None
    MultiModalConversation = None
    HAS_DASHSCOPE = False

from .token_limit import resolve_max_tokens  # noqa: E402


def _resolve_max_tokens() -> int:
    """长内容（教案等）的输出上限。

    教训：这里原先是 4096，而 12 个模块的完整教案输出远超该值，
    会被硬截断（finish_reason='length'）返回不完整 JSON，
    下游解析后得到**全空模块**——表现为"生成成功但内容为空"。
    默认抬到 8192；所有 provider 共用 token_limit.resolve_max_tokens，
    避免同样的坑在其他模型上再来一次。
    """
    return resolve_max_tokens()


class DashScopeProvider(LLMProviderBase):
    """阿里云百炼（通义千问）LLM提供商"""
    
    def test_connection(self, api_key: str, base_url: Optional[str] = None) -> Dict[str, Any]:
        """测试连接与密钥有效性"""
        if not HAS_DASHSCOPE:
            return {'success': False, 'message': '未安装 dashscope SDK，请运行: pip install dashscope'}
        try:
            dashscope.api_key = api_key
            # 测试调用
            response = dashscope.Generation.call(
                model='qwen-turbo',
                prompt='测试连接',
                max_tokens=10
            )
            if response.status_code == 200:
                return {'success': True, 'message': '连接成功'}
            else:
                return {'success': False, 'message': f'连接失败: {response.message}'}
        except Exception as e:
            return {'success': False, 'message': f'连接失败: {str(e)}'}
    
    def list_models(self, api_key: str, base_url: Optional[str] = None) -> List[Dict[str, str]]:
        """获取可用模型列表"""
        if HAS_DASHSCOPE and api_key:
            dashscope.api_key = api_key
        # 阿里云百炼的模型列表
        models = [
            {'name': 'qwen-max', 'description': '通义千问最大模型，最强推理能力'},  
            {'name': 'qwen-plus', 'description': '通义千问增强模型，平衡性能和成本'},
            {'name': 'qwen-turbo', 'description': '通义千问轻量模型，快速响应'},
            {'name': 'qwen-72b-chat', 'description': '72B参数对话模型'},
            {'name': 'qwen-14b-chat', 'description': '14B参数对话模型'}
        ]
        return models
    
    def chat_completions(
        self,
        prompt: str,
        history: List[Dict],
        temperature: float = 0.7,
        api_key: str = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> str:
        """统一的对话生成方法"""
        if not HAS_DASHSCOPE:
            return '生成失败: 未安装 dashscope SDK，请运行: pip install dashscope'
        dashscope.api_key = api_key
        
        # 构建对话历史
        messages = []
        for item in history:
            if item.get('role') == 'user':
                messages.append({'role': 'user', 'content': item.get('content', '')})
            elif item.get('role') == 'assistant':
                messages.append({'role': 'assistant', 'content': item.get('content', '')})
        
        # 添加当前提示
        messages.append({'role': 'user', 'content': prompt})
        
        try:
            response = dashscope.Generation.call(
                model=model or 'qwen-max',
                messages=messages,
                **sampling_kwargs(temperature),
                max_tokens=_resolve_max_tokens()  # 教案等长内容生成需要更多token
            )
            
            if response.status_code == 200:
                return response.output.text
            else:
                return f'生成失败: {response.message}'
        except Exception as e:
            return f'生成失败: {str(e)}'
    
    def get_embeddings(
        self,
        text: str,
        api_key: str = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> List[float]:
        """获取文本嵌入向量"""
        if not HAS_DASHSCOPE:
            return [0.0] * 768
        dashscope.api_key = api_key
        
        try:
            response = dashscope.TextEmbedding.call(
                model=model or 'text-embedding-v1',
                input=text
            )
            
            if response.status_code == 200:
                return response.output['embeddings'][0]['embedding']
            else:
                raise Exception(f'嵌入生成失败: {response.message}')
        except Exception as e:
            # 失败时返回默认向量
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
        if not HAS_DASHSCOPE:
            yield '生成失败: 未安装 dashscope SDK，请运行: pip install dashscope'
            return
        dashscope.api_key = api_key
        
        # 构建对话历史
        messages = []
        for item in history:
            if item.get('role') == 'user':
                messages.append({'role': 'user', 'content': item.get('content', '')})
            elif item.get('role') == 'assistant':
                messages.append({'role': 'assistant', 'content': item.get('content', '')})
        
        # 添加当前提示
        messages.append({'role': 'user', 'content': prompt})
        
        try:
            response = dashscope.Generation.call(
                model=model or 'qwen-max',
                messages=messages,
                **sampling_kwargs(temperature),
                max_tokens=2048,
                stream=True
            )
            
            # 处理流式响应（DashScope返回累积文本，需要计算增量）
            full_response = ""
            for chunk in response:
                if chunk.status_code == 200 and chunk.output and chunk.output.text:
                    delta = chunk.output.text[len(full_response):]
                    if delta:
                        yield delta
                    full_response = chunk.output.text
        except Exception as e:
            yield f'生成失败: {str(e)}'

    def stream_vision_chat(
        self,
        prompt: str,
        image_base64: str,
        history: List[Dict] = None,
        temperature: float = 0.7,
        api_key: str = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Generator[str, None, None]:
        """DashScope视觉多模态流式对话 - 使用MultiModalConversation API"""
        if not HAS_DASHSCOPE or MultiModalConversation is None:
            yield '生成失败: 未安装 dashscope SDK，请运行: pip install dashscope'
            return
        dashscope.api_key = api_key

        # 构建多模态消息
        messages = []
        for item in (history or []):
            if item.get('role') in ('user', 'assistant'):
                messages.append({'role': item['role'], 'content': [{'text': item.get('content', '')}]})

        # 添加带图片的用户消息
        user_content = [
            {'image': f'data:image/png;base64,{image_base64}'},
            {'text': prompt},
        ]
        messages.append({'role': 'user', 'content': user_content})

        # 选择视觉模型
        vision_model = model or 'qwen-vl-plus'

        try:
            responses = MultiModalConversation.call(
                model=vision_model,
                messages=messages,
                stream=True,
            )

            full_response = ""
            for chunk in responses:
                if chunk.status_code == 200 and chunk.output:
                    choices = chunk.output.get('choices', [])
                    if choices:
                        content_list = choices[0].get('message', {}).get('content', [])
                        current_text = ''
                        for item in content_list:
                            if isinstance(item, dict) and 'text' in item:
                                current_text += item['text']
                        if current_text and len(current_text) > len(full_response):
                            delta = current_text[len(full_response):]
                            yield delta
                            full_response = current_text
        except Exception as e:
            yield f'图片识别失败: {str(e)}'
