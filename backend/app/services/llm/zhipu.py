"""智谱AI（GLM）LLM实现"""
import requests
from typing import List, Dict, Optional, Any, Generator
from .base import LLMProviderBase
from .token_limit import resolve_max_tokens

class ZhipuProvider(LLMProviderBase):
    """智谱AI（GLM）LLM提供商"""
    
    # 智谱AI API配置
    DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
    
    def test_connection(self, api_key: str, base_url: Optional[str] = None) -> Dict[str, Any]:
        """测试连接与密钥有效性"""
        try:
            url = f"{base_url or self.DEFAULT_BASE_URL}/models"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                return {'success': True, 'message': '智谱AI连接成功'}
            else:
                error_msg = response.json().get('error', {}).get('message', '未知错误')
                return {'success': False, 'message': f'连接失败: {error_msg}'}
        except requests.exceptions.Timeout:
            return {'success': False, 'message': '连接超时，请检查网络'}
        except requests.exceptions.ConnectionError:
            return {'success': False, 'message': '无法连接到智谱AI服务，请检查API地址'}
        except Exception as e:
            return {'success': False, 'message': f'连接失败: {str(e)}'}
    
    def list_models(self, api_key: str, base_url: Optional[str] = None) -> List[Dict[str, str]]:
        """获取可用模型列表"""
        # 智谱AI常用模型
        models = [
            {'name': 'glm-4', 'description': 'GLM-4 最强对话模型'},
            {'name': 'glm-4-plus', 'description': 'GLM-4 Plus 增强版'},
            {'name': 'glm-4-air', 'description': 'GLM-4 Air 高性价比'},
            {'name': 'glm-4-flash', 'description': 'GLM-4 Flash 快速响应'},
            {'name': 'glm-3-turbo', 'description': 'GLM-3 Turbo'},
            {'name': 'cogview-3', 'description': 'CogView-3 图像生成'}
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
        url = f"{base_url or self.DEFAULT_BASE_URL}/chat/completions"
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
            "model": model or "glm-4",
            "messages": messages,
            "temperature": temperature,
            # 长内容（教案等）需足够大的输出上限，否则被截断会导致内容全空
            "max_tokens": resolve_max_tokens()
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=120)
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
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
        url = f"{base_url or self.DEFAULT_BASE_URL}/embeddings"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "embedding-2",
            "input": text
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            if response.status_code == 200:
                result = response.json()
                return result['data'][0]['embedding']
            else:
                return [0.0] * 768
        except Exception:
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
        url = f"{base_url or self.DEFAULT_BASE_URL}/chat/completions"
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
            "model": model or "glm-4",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 2048,
            "stream": True
        }
        
        try:
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
                        except Exception:
                            pass
        except Exception as e:
            yield f'生成失败: {str(e)}'
