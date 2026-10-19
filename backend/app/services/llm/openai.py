"""OpenAI LLM实现"""
from typing import List, Dict, Optional, Any, Generator
from .base import LLMProviderBase, sampling_kwargs
from .token_limit import resolve_max_tokens

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    OpenAI = None
    HAS_OPENAI = False

class OpenAIProvider(LLMProviderBase):
    """OpenAI LLM提供商"""
    
    def test_connection(self, api_key: str, base_url: Optional[str] = None) -> Dict[str, Any]:
        """测试连接与密钥有效性"""
        if not HAS_OPENAI:
            return {'success': False, 'message': '未安装 openai SDK，请运行: pip install openai'}
        try:
            client = OpenAI(
                api_key=api_key,
                base_url=base_url or "https://api.openai.com/v1"
            )
            # 测试调用
            models = client.models.list()
            return {'success': True, 'message': '连接成功'}
        except Exception as e:
            return {'success': False, 'message': f'连接失败: {str(e)}'}
    
    def list_models(self, api_key: str, base_url: Optional[str] = None) -> List[Dict[str, str]]:
        """获取可用模型列表"""
        try:
            client = OpenAI(
                api_key=api_key,
                base_url=base_url or "https://api.openai.com/v1"
            )
            response = client.models.list()
            models = []
            for model in response.data:
                models.append({
                    'name': model.id,
                    'description': model.name or 'OpenAI模型'
                })
            return models
        except Exception as e:
            # 失败时返回默认模型列表
            return [
                {'name': 'gpt-4', 'description': 'GPT-4 模型'},  
                {'name': 'gpt-4-turbo', 'description': 'GPT-4 Turbo 模型'},
                {'name': 'gpt-3.5-turbo', 'description': 'GPT-3.5 Turbo 模型'},
                {'name': 'gpt-3.5-turbo-16k', 'description': 'GPT-3.5 Turbo 16K 模型'}
            ]
    
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
        if not HAS_OPENAI:
            return '生成失败: 未安装 openai SDK，请运行: pip install openai'
        try:
            client = OpenAI(
                api_key=api_key,
                base_url=base_url or "https://api.openai.com/v1"
            )
            
            # 构建对话历史
            messages = []
            for item in history:
                if item.get('role') == 'user':
                    messages.append({'role': 'user', 'content': item.get('content', '')})
                elif item.get('role') == 'assistant':
                    messages.append({'role': 'assistant', 'content': item.get('content', '')})
            
            # 添加当前提示
            messages.append({'role': 'user', 'content': prompt})
            
            response = client.chat.completions.create(
                model=model or "gpt-3.5-turbo",
                messages=messages,
                **sampling_kwargs(temperature),
                # 教案等长内容需足够大的输出上限，否则会被截断成不完整 JSON
                max_tokens=resolve_max_tokens(),
                timeout=120  # 教案等长内容生成需要更长时间
            )
            
            return response.choices[0].message.content
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
        if not HAS_OPENAI:
            return [0.0] * 1536
        try:
            client = OpenAI(
                api_key=api_key,
                base_url=base_url or "https://api.openai.com/v1"
            )
            
            response = client.embeddings.create(
                model=model or "text-embedding-3-small",
                input=text
            )
            
            return response.data[0].embedding
        except Exception as e:
            # 失败时返回默认向量
            return [0.0] * 1536
    
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
        if not HAS_OPENAI:
            yield '生成失败: 未安装 openai SDK，请运行: pip install openai'
            return
        try:
            client = OpenAI(
                api_key=api_key,
                base_url=base_url or "https://api.openai.com/v1"
            )
            
            # 构建对话历史
            messages = []
            for item in history:
                if item.get('role') == 'user':
                    messages.append({'role': 'user', 'content': item.get('content', '')})
                elif item.get('role') == 'assistant':
                    messages.append({'role': 'assistant', 'content': item.get('content', '')})
            
            # 添加当前提示
            messages.append({'role': 'user', 'content': prompt})
            
            stream = client.chat.completions.create(
                model=model or "gpt-3.5-turbo",
                messages=messages,
                **sampling_kwargs(temperature),
                max_tokens=2048,
                stream=True
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            yield f'生成失败: {str(e)}'