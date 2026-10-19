"""Google Gemini LLM实现"""
import requests
import json
from typing import List, Dict, Optional, Any, Generator
from .base import LLMProviderBase, sampling_kwargs

class GeminiProvider(LLMProviderBase):
    """Google Gemini LLM提供商"""
    
    # Gemini API配置
    DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
    
    def test_connection(self, api_key: str, base_url: Optional[str] = None) -> Dict[str, Any]:
        """测试连接与密钥有效性"""
        try:
            url = f"{base_url or self.DEFAULT_BASE_URL}/models?key={api_key}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                return {'success': True, 'message': 'Google Gemini连接成功'}
            else:
                error_msg = response.json().get('error', {}).get('message', '未知错误')
                return {'success': False, 'message': f'连接失败: {error_msg}'}
        except requests.exceptions.Timeout:
            return {'success': False, 'message': '连接超时，请检查网络'}
        except requests.exceptions.ConnectionError:
            return {'success': False, 'message': '无法连接到Google Gemini服务，请检查网络'}
        except Exception as e:
            return {'success': False, 'message': f'连接失败: {str(e)}'}
    
    def list_models(self, api_key: str, base_url: Optional[str] = None) -> List[Dict[str, str]]:
        """获取可用模型列表"""
        # Google Gemini常用模型
        models = [
            {'name': 'gemini-2.0-flash', 'description': 'Gemini 2.0 Flash 最新快速模型'},
            {'name': 'gemini-1.5-pro', 'description': 'Gemini 1.5 Pro 最强推理'},
            {'name': 'gemini-1.5-flash', 'description': 'Gemini 1.5 Flash 高性价比'},
            {'name': 'gemini-1.5-flash-8b', 'description': 'Gemini 1.5 Flash 8B 轻量版'},
            {'name': 'gemini-pro', 'description': 'Gemini Pro 标准版'}
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
        model_name = model or "gemini-1.5-flash"
        url = f"{base_url or self.DEFAULT_BASE_URL}/models/{model_name}:generateContent?key={api_key}"
        headers = {
            "Content-Type": "application/json"
        }
        
        # 构建对话历史
        contents = []
        for item in history:
            if item.get('role') == 'user':
                contents.append({
                    "role": "user",
                    "parts": [{"text": item.get('content', '')}]
                })
            elif item.get('role') == 'assistant':
                contents.append({
                    "role": "model",
                    "parts": [{"text": item.get('content', '')}]
                })
        
        # 添加当前提示
        contents.append({
            "role": "user",
            "parts": [{"text": prompt}]
        })
        
        data = {
            "contents": contents,
            "generationConfig": {
                **sampling_kwargs(temperature),
                "maxOutputTokens": 2048
            }
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            if response.status_code == 200:
                result = response.json()
                if result.get('candidates') and result['candidates'][0].get('content'):
                    return result['candidates'][0]['content']['parts'][0]['text']
                return "未能生成有效响应"
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
        model_name = "embedding-001"
        url = f"{base_url or self.DEFAULT_BASE_URL}/models/{model_name}:embedContent?key={api_key}"
        headers = {
            "Content-Type": "application/json"
        }
        
        data = {
            "model": model_name,
            "content": {
                "parts": [{"text": text}]
            }
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            if response.status_code == 200:
                result = response.json()
                if result.get('embedding'):
                    return result['embedding']['values']
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
        model_name = model or "gemini-1.5-flash"
        url = f"{base_url or self.DEFAULT_BASE_URL}/models/{model_name}:streamGenerateContent?key={api_key}&alt=sse"
        headers = {
            "Content-Type": "application/json"
        }
        
        # 构建对话历史
        contents = []
        for item in history:
            if item.get('role') == 'user':
                contents.append({
                    "role": "user",
                    "parts": [{"text": item.get('content', '')}]
                })
            elif item.get('role') == 'assistant':
                contents.append({
                    "role": "model",
                    "parts": [{"text": item.get('content', '')}]
                })
        
        # 添加当前提示
        contents.append({
            "role": "user",
            "parts": [{"text": prompt}]
        })
        
        data = {
            "contents": contents,
            "generationConfig": {
                **sampling_kwargs(temperature),
                "maxOutputTokens": 2048
            }
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, stream=True, timeout=60)
            for chunk in response.iter_lines():
                if chunk:
                    try:
                        line = chunk.decode('utf-8')
                        # Gemini SSE格式: "data: {json}" 需要剥离前缀
                        if line.startswith('data: '):
                            line = line[6:]
                        data = json.loads(line)
                        if data.get('candidates') and data['candidates'][0].get('content'):
                            content = data['candidates'][0]['content']['parts'][0].get('text', '')
                            if content:
                                yield content
                    except Exception:
                        pass
        except Exception as e:
            yield f'生成失败: {str(e)}'
