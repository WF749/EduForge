"""本地模型LLM实现"""
import requests
from typing import List, Dict, Optional, Any, Generator
from .base import LLMProviderBase, sampling_kwargs
from .token_limit import resolve_max_tokens

class LocalModelProvider(LLMProviderBase):
    """本地模型LLM提供商"""

    def __init__(self):
        """初始化本地模型提供商"""
        # 支持的本地模型部署方案
        self.local_providers = {
            'ollama': {
                'name': 'Ollama',
                # Windows 上 localhost 可能优先解析到 IPv6 ::1，导致连接被拒绝；默认用 IPv4 更稳
                'default_url': 'http://127.0.0.1:11434',
                'description': '轻量级本地模型部署工具，适合个人使用'
            },
            'vllm': {
                'name': 'vLLM',
                'default_url': 'http://localhost:8000/v1',
                'description': '高性能推理引擎，适合生产环境'
            }
        }

    def detect_provider(self, base_url: Optional[str] = None) -> str:
        """检测本地模型提供商类型"""
        if base_url:
            if '11434' in base_url or 'ollama' in base_url.lower():
                return 'ollama'
            elif '8000' in base_url or 'vllm' in base_url.lower():
                return 'vllm'
        return 'ollama'  # 默认返回ollama

    def get_default_url(self, provider: str) -> str:
        """获取默认URL"""
        return self.local_providers.get(provider, self.local_providers['ollama'])['default_url']

    def test_connection(self, api_key: str, base_url: Optional[str] = None) -> Dict[str, Any]:
        """测试连接与密钥有效性"""
        try:
            # 检测提供商类型
            provider = self.detect_provider(base_url)
            # 获取默认URL
            default_url = self.get_default_url(provider)
            # 使用用户提供的URL或默认URL
            actual_url = base_url or default_url

            if provider == 'ollama':
                # Ollama API端点是 /api/tags
                url = f"{actual_url}/api/tags"
            else:
                # vLLM使用OpenAI兼容的API
                url = f"{actual_url}/models"

            headers = {
                "Content-Type": "application/json"
            }
            # 本地模型不需要API Key
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                return {'success': True, 'message': f'{self.local_providers[provider]["name"]} 连接成功'}
            else:
                return {'success': False, 'message': f'连接失败: {response.text}'}
        except requests.exceptions.ConnectionError as e:
            msg = str(e)
            # Windows 常见：目标计算机积极拒绝（10061）= 服务没启动/端口没监听
            if "WinError 10061" in msg or "actively refused" in msg:
                hint = (
                    "连接被拒绝（通常是服务未启动或端口未监听）。\n"
                    "请按下面步骤处理（任选其一即可）：\n"
                    "1）如果你装的是 Windows 版 Ollama：打开 Ollama 应用后重试；或在命令行执行 `ollama list` 确认可用。\n"
                    "2）如果你是在 WSL/Linux 里跑 Ollama：需要让它监听 0.0.0.0（例如设置 OLLAMA_HOST=0.0.0.0:11434），并在设置里把地址改成你 WSL 的实际可访问地址。\n"
                    "3）快速自检：在 PowerShell 执行 `irm http://localhost:11434/api/tags`，能返回 JSON 才表示服务真的起来了。"
                )
                return {'success': False, 'message': f'连接失败: {msg}\n\n{hint}'}
            return {'success': False, 'message': f'连接失败: {msg}'}
        except Exception as e:
            return {'success': False, 'message': f'连接失败: {str(e)}'}

    def list_models(self, api_key: str, base_url: Optional[str] = None) -> List[Dict[str, str]]:
        """获取可用模型列表"""
        try:
            # 检测提供商类型
            provider = self.detect_provider(base_url)
            # 获取默认URL
            default_url = self.get_default_url(provider)
            # 使用用户提供的URL或默认URL
            actual_url = base_url or default_url

            if provider == 'ollama':
                # Ollama API端点是 /api/tags
                url = f"{actual_url}/api/tags"
            else:
                # vLLM使用OpenAI兼容的API
                url = f"{actual_url}/models"

            headers = {
                "Content-Type": "application/json"
            }
            # 本地模型不需要API Key
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                models = []

                if provider == 'ollama':
                    # Ollama返回的格式: {"models": [{"name": "model-name", ...}]}
                    for model in data.get('models', []):
                        model_name = model.get('name', '')
                        models.append({
                            'name': model_name,
                            'description': f'{model_name} 模型'
                        })
                else:
                    # vLLM使用OpenAI兼容格式: {"data": [{"id": "model-name", ...}]}
                    for model in data.get('data', []):
                        models.append({
                            'name': model.get('id'),
                            'description': model.get('name', '本地模型')
                        })

                return models if models else self._get_default_models()
            else:
                # 失败时返回默认模型列表
                return self._get_default_models()
        except Exception as e:
            # 失败时返回默认模型列表
            return self._get_default_models()

    def _get_default_models(self) -> List[Dict[str, str]]:
        """获取默认模型列表"""
        return [
            {'name': 'llama3', 'description': 'Llama 3 模型'},
            {'name': 'gemma', 'description': 'Gemma 模型'},
            {'name': 'mistral', 'description': 'Mistral 模型'},
            {'name': 'phi3', 'description': 'Phi 3 模型'}
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
        try:
            # 检测提供商类型
            provider = self.detect_provider(base_url)
            # 获取默认URL
            default_url = self.get_default_url(provider)
            # 使用用户提供的URL或默认URL
            actual_url = base_url or default_url

            if provider == 'ollama':
                # Ollama API端点是 /api/generate
                url = f"{actual_url}/api/generate"

                # 构建提示词（包含历史对话）
                full_prompt = self._build_prompt_with_history(prompt, history)

                # 如果model是auto，自动检测Ollama中存在的模型
                if model == 'auto':
                    try:
                        # 获取Ollama中存在的模型
                        tags_url = f"{actual_url}/api/tags"
                        response = requests.get(tags_url, timeout=10)
                        if response.status_code == 200:
                            data = response.json()
                            if data.get('models') and len(data['models']) > 0:
                                model = data['models'][0]['name']
                            else:
                                model = "qwen3-coder:30b"
                    except:
                        model = "qwen3-coder:30b"
                data = {
                    "model": model or "qwen3-coder:30b",
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {
                        **sampling_kwargs(temperature),
                    }
                }

                headers = {
                    "Content-Type": "application/json"
                }

                response = requests.post(url, headers=headers, json=data, timeout=30)
                if response.status_code == 200:
                    result = response.json()
                    return result.get('response', '')
                else:
                    return f'生成失败: {response.text}'
            else:
                # vLLM使用OpenAI兼容的API
                url = f"{actual_url}/chat/completions"
                headers = {
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
                    "model": model or "llama3",
                    "messages": messages,
                    **sampling_kwargs(temperature),
                    # 校内模型同样要防截断：输出被截会让教案内容整片为空
                    "max_tokens": resolve_max_tokens()
                }

                response = requests.post(url, headers=headers, json=data, timeout=30)
                if response.status_code == 200:
                    return response.json()['choices'][0]['message']['content']
                else:
                    return f'生成失败: {response.text}'
        except Exception as e:
            return f'生成失败: {str(e)}'

    def _build_prompt_with_history(self, prompt: str, history: List[Dict]) -> str:
        """构建包含历史对话的提示词"""
        # 使用更适合Ollama模型的提示词格式
        full_prompt = """
你是一个智能助手，能够提供详细、准确、结构清晰的回答。请根据用户的问题，提供全面而有条理的回答，包括必要的细节和示例。

对话历史：
"""

        # 添加历史对话
        for item in history:
            role = item.get('role', '')
            content = item.get('content', '')
            if role == 'user':
                full_prompt += f"用户: {content}\n"
            elif role == 'assistant':
                full_prompt += f"助手: {content}\n"

        # 添加当前提示
        full_prompt += f"\n用户: {prompt}\n\n助手:"

        return full_prompt

    def get_embeddings(
        self,
        text: str,
        api_key: str = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> List[float]:
        """获取文本嵌入向量"""
        try:
            # 检测提供商类型
            provider = self.detect_provider(base_url)
            # 获取默认URL
            default_url = self.get_default_url(provider)
            # 使用用户提供的URL或默认URL
            actual_url = base_url or default_url

            if provider == 'ollama':
                # Ollama嵌入API
                url = f"{actual_url}/api/embeddings"
                headers = {
                    "Content-Type": "application/json"
                }

                data = {
                    "model": model or "llama3",
                    "prompt": text
                }

                response = requests.post(url, headers=headers, json=data, timeout=30)
                if response.status_code == 200:
                    result = response.json()
                    return result.get('embedding', [0.0] * 768)
                else:
                    # 失败时返回默认向量
                    return [0.0] * 768
            else:
                # vLLM使用OpenAI兼容的API
                url = f"{actual_url}/embeddings"
                headers = {
                    "Content-Type": "application/json"
                }

                data = {
                    "model": model or "llama3",
                    "input": text
                }

                response = requests.post(url, headers=headers, json=data, timeout=30)
                if response.status_code == 200:
                    return response.json()['data'][0]['embedding']
                else:
                    # 失败时返回默认向量
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
            # 检测提供商类型
            local_provider = self.detect_provider(base_url)
            # 获取默认URL
            default_url = self.get_default_url(local_provider)
            # 使用用户提供的URL或默认URL
            actual_url = base_url or default_url

            if local_provider == 'ollama':
                # Ollama API端点是 /api/generate
                url = f"{actual_url}/api/generate"

                # 构建提示词（包含历史对话）
                full_prompt = self._build_prompt_with_history(prompt, history)

                # 如果model是auto或None，自动检测Ollama中存在的模型
                if model == 'auto' or model is None:
                    try:
                        # 获取Ollama中存在的模型
                        tags_url = f"{actual_url}/api/tags"
                        response = requests.get(tags_url, timeout=10)
                        if response.status_code == 200:
                            data = response.json()
                            if data.get('models') and len(data['models']) > 0:
                                model = data['models'][0]['name']
                            else:
                                model = "qwen3-coder:30b"
                    except:
                        model = "qwen3-coder:30b"
                data = {
                    "model": model or "qwen3-coder:30b",
                    "prompt": full_prompt,
                    "stream": True,
                    "options": {
                        **sampling_kwargs(temperature),
                    }
                }

                headers = {
                    "Content-Type": "application/json"
                }

                response = requests.post(url, headers=headers, json=data, stream=True, timeout=30)
                for line in response.iter_lines():
                    if line:
                        try:
                            import json
                            line_str = line.decode('utf-8')
                            data = json.loads(line_str)
                            if 'response' in data:
                                # Ollama流式模式下response字段是增量文本（每次只包含新token）
                                token = data['response']
                                if token:
                                    yield token
                            # 检查是否结束
                            if data.get('done'):
                                break
                        except Exception as e:
                            print(f"Error processing chunk: {e}")
                            pass
            else:
                # vLLM使用OpenAI兼容的API
                url = f"{actual_url}/chat/completions"
                headers = {
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
                    "model": model or "llama3",
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
