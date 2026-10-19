"""DeepSeek LLM实现"""
import requests
from typing import List, Dict, Optional, Any, Generator
from .base import LLMProviderBase, sampling_kwargs
from .token_limit import resolve_max_tokens

class DeepSeekProvider(LLMProviderBase):
    """DeepSeek LLM提供商"""
    
    def test_connection(self, api_key: str, base_url: Optional[str] = None) -> Dict[str, Any]:
        """测试连接与密钥有效性"""
        try:
            url = (base_url or "https://api.deepseek.com/v1").rstrip("/") + "/models"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                return {'success': True, 'message': '连接成功'}
            else:
                return {'success': False, 'message': f'连接失败: {response.text}'}
        except Exception as e:
            return {'success': False, 'message': f'连接失败: {str(e)}'}
    
    def list_models(self, api_key: str, base_url: Optional[str] = None) -> List[Dict[str, str]]:
        """获取可用模型列表"""
        try:
            url = (base_url or "https://api.deepseek.com/v1").rstrip("/") + "/models"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                models = []
                for model in data.get('data', []):
                    models.append({
                        'name': model.get('id'),
                        'description': model.get('name', 'DeepSeek模型')
                    })
                return models
            else:
                # 失败时返回默认模型列表
                return [
                    {'name': 'deepseek-chat', 'description': 'DeepSeek 对话模型'},
                    {'name': 'deepseek-coder', 'description': 'DeepSeek 代码模型'},
                    {'name': 'deepseek-llm', 'description': 'DeepSeek 通用大语言模型'}
                ]
        except Exception as e:
            # 失败时返回默认模型列表
            return [
                {'name': 'deepseek-chat', 'description': 'DeepSeek 对话模型'},
                {'name': 'deepseek-coder', 'description': 'DeepSeek 代码模型'},
                {'name': 'deepseek-llm', 'description': 'DeepSeek 通用大语言模型'}
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
        url = (base_url or "https://api.deepseek.com/v1").rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
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
            "model": model or "deepseek-chat",
            "messages": messages,
            **sampling_kwargs(temperature),
            # 长内容（教案等）需足够大的输出上限，否则被截断会导致内容全空
            "max_tokens": resolve_max_tokens()
        }

        # 第一次尝试：120秒超时
        try:
            response = requests.post(url, headers=headers, json=data, timeout=120)
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
            elif response.status_code == 429:
                # 限流，抛出异常让上层重试
                raise Exception(f"DeepSeek API 限流 (429): {response.text[:200]}")
            else:
                raise Exception(f"DeepSeek API 错误 ({response.status_code}): {response.text[:200]}")
        except requests.exceptions.Timeout:
            raise Exception("DeepSeek API 请求超时 (120s)")
        except requests.exceptions.ConnectionError as e:
            raise Exception(f"DeepSeek API 连接失败: {str(e)[:200]}")
    
    def get_embeddings(
        self,
        text: str,
        api_key: str = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> List[float]:
        """获取文本嵌入向量"""
        try:
            # DeepSeek 目前没有公开的嵌入API，使用默认向量
            return [0.0] * 768
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
        try:
            url = (base_url or "https://api.deepseek.com/v1").rstrip("/") + "/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
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
                "model": model or "deepseek-chat",
                "messages": messages,
                **sampling_kwargs(temperature),
                "max_tokens": 2048,
                "stream": True
            }
            
            response = requests.post(url, headers=headers, json=data, stream=True, timeout=30)
            for chunk in response.iter_lines():
                if chunk:
                    chunk = chunk.decode('utf-8')
                    if chunk.startswith('data: '):
                        chunk = chunk[6:]
                        if chunk == '[DONE]':
                            break
                        try:
                            import json
                            data = json.loads(chunk)
                            if data.get('choices') and data['choices'][0].get('delta'):
                                content = data['choices'][0]['delta'].get('content')
                                if content:
                                    yield content
                        except:
                            pass
        except Exception as e:
            yield f'生成失败: {str(e)}'