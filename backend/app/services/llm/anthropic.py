"""Anthropic Claude LLM实现"""
import requests
from typing import List, Dict, Optional, Any, Generator
from .base import LLMProviderBase
from .token_limit import resolve_max_tokens

class AnthropicProvider(LLMProviderBase):
    """Anthropic Claude LLM提供商"""
    
    # Claude API配置
    DEFAULT_BASE_URL = "https://api.anthropic.com/v1"
    DEFAULT_API_VERSION = "2023-06-01"
    
    def test_connection(self, api_key: str, base_url: Optional[str] = None) -> Dict[str, Any]:
        """测试连接与密钥有效性"""
        try:
            url = f"{base_url or self.DEFAULT_BASE_URL}/messages"
            headers = {
                "x-api-key": api_key,
                "anthropic-version": self.DEFAULT_API_VERSION,
                "Content-Type": "application/json"
            }
            
            # 发送一个简单的测试请求
            data = {
                "model": "claude-3-haiku-20240307",
                "max_tokens": 10,
                "messages": [{"role": "user", "content": "test"}]
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=10)
            if response.status_code == 200:
                return {'success': True, 'message': 'Anthropic Claude连接成功'}
            else:
                error_msg = response.json().get('error', {}).get('message', '未知错误')
                return {'success': False, 'message': f'连接失败: {error_msg}'}
        except requests.exceptions.Timeout:
            return {'success': False, 'message': '连接超时，请检查网络'}
        except requests.exceptions.ConnectionError:
            return {'success': False, 'message': '无法连接到Anthropic Claude服务，请检查网络'}
        except Exception as e:
            return {'success': False, 'message': f'连接失败: {str(e)}'}
    
    def list_models(self, api_key: str, base_url: Optional[str] = None) -> List[Dict[str, str]]:
        """获取可用模型列表"""
        # Anthropic Claude常用模型
        models = [
            {'name': 'claude-3-5-sonnet-latest', 'description': 'Claude 3.5 Sonnet 最新最强'},
            {'name': 'claude-3-5-sonnet-20241022', 'description': 'Claude 3.5 Sonnet'},
            {'name': 'claude-3-opus-latest', 'description': 'Claude 3 Opus 最强推理'},
            {'name': 'claude-3-haiku-latest', 'description': 'Claude 3 Haiku 快速响应'},
            {'name': 'claude-3-sonnet-latest', 'description': 'Claude 3 Sonnet 平衡'}
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
        url = f"{base_url or self.DEFAULT_BASE_URL}/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": self.DEFAULT_API_VERSION,
            "Content-Type": "application/json"
        }
        
        # 构建对话历史
        messages = []
        for item in history:
            if item.get('role') == 'user':
                messages.append({'role': 'user', 'content': item.get('content', '')})
            elif item.get('role') == 'assistant':
                messages.append({'role': 'assistant', 'content': item.get('content', '')})
        
        # 添加当前提示
        messages.append({'role': 'user', 'content': prompt})
        
        data = {
            "model": model or "claude-3-5-sonnet-latest",
            "messages": messages,
            "temperature": temperature,
            # 教案等长内容需足够大的输出上限，否则会被截断成不完整 JSON
            "max_tokens": resolve_max_tokens()
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            if response.status_code == 200:
                result = response.json()
                return result['content'][0]['text']
            else:
                error_msg = response.json().get('error', {}).get('message', '未知错误')
                return f'生成失败: {error_msg}'
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
        # Claude本身不提供嵌入功能，返回默认向量
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
        url = f"{base_url or self.DEFAULT_BASE_URL}/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": self.DEFAULT_API_VERSION,
            "Content-Type": "application/json"
        }
        
        # 构建对话历史
        messages = []
        for item in history:
            if item.get('role') == 'user':
                messages.append({'role': 'user', 'content': item.get('content', '')})
            elif item.get('role') == 'assistant':
                messages.append({'role': 'assistant', 'content': item.get('content', '')})
        
        # 添加当前提示
        messages.append({'role': 'user', 'content': prompt})
        
        data = {
            "model": model or "claude-3-5-sonnet-latest",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 2048,
            "stream": True
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, stream=True, timeout=60)
            for chunk in response.iter_lines():
                if chunk:
                    chunk = chunk.decode('utf-8')
                    if chunk.startswith('data: '):
                        chunk = chunk[6:]
                        try:
                            import json
                            data = json.loads(chunk)
                            if data.get('type') == 'content_block_delta':
                                if data.get('delta', {}).get('type') == 'text_delta':
                                    yield data['delta'].get('text', '')
                        except Exception:
                            pass
        except Exception as e:
            yield f'生成失败: {str(e)}'
