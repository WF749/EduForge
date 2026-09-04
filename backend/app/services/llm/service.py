"""LLM服务全局单例调用入口"""
from typing import List, Dict, Optional, Any, Generator
from .base import LLMProviderBase
from .dashscope import DashScopeProvider
from .openai import OpenAIProvider
from .deepseek import DeepSeekProvider
from .local import LocalModelProvider
from .demo import DemoProvider
from .zhipu import ZhipuProvider
from .gemini import GeminiProvider
from .anthropic import AnthropicProvider
from .moonshot import MoonshotProvider
from ...core.crypto import crypto_utils
from ...core.config import settings
from ...core.errors import DataEgressBlockedError
from ...core.harness.exceptions import LLMUnavailableError
import sqlite3
import os


def _guard(*, prompt: str, history: List[Dict], base_url: str, provider: str) -> Dict[str, Any]:
    """数据流向判定。实现统一在 app/safety/guard.py，与 llm_client 共用。"""
    from ...safety.guard import guard_flow

    return guard_flow(prompt=prompt, history=history, base_url=base_url, provider=provider)


def _guard_notice(flow: Dict[str, Any]) -> str:
    from ...safety.guard import block_notice

    return block_notice(flow)


def _redact_text(text: str) -> str:
    from ...safety.redact import redact

    return redact(text)[0]


def _redact_history(history: Optional[List[Dict]]) -> List[Dict]:
    """脱敏历史消息，仅处理文本型 content。"""
    if not history:
        return []
    out: List[Dict] = []
    for h in history:
        content = h.get("content")
        if isinstance(content, str):
            out.append({**h, "content": _redact_text(content)})
        else:
            out.append(h)
    return out


class LLMService:
    """LLM服务全局单例"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LLMService, cls).__new__(cls)
            cls._instance._init()
        return cls._instance
    
    def _init(self):
        """初始化服务"""
        self.providers = {
            'dashscope': DashScopeProvider(),
            'openai': OpenAIProvider(),
            'deepseek': DeepSeekProvider(),
            'local': LocalModelProvider(),
            'demo': DemoProvider(),
            'zhipu': ZhipuProvider(),
            'gemini': GeminiProvider(),
            'anthropic': AnthropicProvider(),
            'moonshot': MoonshotProvider(),
        }
        # 数据库统一放在 backend/llm_config.db（避免出现 backend/app/llm_config.db 和 backend/llm_config.db 两份）
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
        self.db_path = os.path.join(backend_dir, "llm_config.db")
        self._api_key_col = "api_key"
        self._last_db_error: Optional[str] = None
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        """创建数据库连接（尽量降低锁冲突）"""
        # timeout：避免瞬时并发写导致 database is locked
        conn = sqlite3.connect(self.db_path, timeout=30)
        try:
            # WAL：提高并发读写能力（SQLite）
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
        except Exception:
            # 某些环境可能不允许修改 pragma，忽略即可
            pass
        return conn
    
    def _init_db(self):
        """初始化数据库"""
        conn = self._connect()
        cursor = conn.cursor()

        # 1) 创建表（新安装场景）
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                api_key TEXT,
                base_url TEXT,
                model TEXT,
                temperature REAL DEFAULT 0.7,
                is_active INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 2) 兼容旧表：检查列并补齐/适配列名
        cursor.execute("PRAGMA table_info(llm_config)")
        cols = {row[1] for row in cursor.fetchall()}

        # 旧版可能用 api_key_encrypted 字段（SQLAlchemy 模型）
        if "api_key" not in cols and "api_key_encrypted" in cols:
            self._api_key_col = "api_key_encrypted"
        else:
            self._api_key_col = "api_key"

        # base_url / model / temperature / is_active 这些列在旧库里可能缺失
        if "base_url" not in cols:
            cursor.execute("ALTER TABLE llm_config ADD COLUMN base_url TEXT")
        if "model" not in cols:
            cursor.execute("ALTER TABLE llm_config ADD COLUMN model TEXT")
        if "temperature" not in cols:
            cursor.execute("ALTER TABLE llm_config ADD COLUMN temperature REAL DEFAULT 0.7")
        if "is_active" not in cols:
            cursor.execute("ALTER TABLE llm_config ADD COLUMN is_active INTEGER DEFAULT 0")

        # 初始化默认提供商行（如果不存在）
        for provider in ("dashscope", "openai", "deepseek", "local", "demo", "zhipu", "gemini", "anthropic", "moonshot"):
            cursor.execute("SELECT 1 FROM llm_config WHERE provider = ?", (provider,))
            if cursor.fetchone() is None:
                cursor.execute(
                    """
                    INSERT INTO llm_config (provider, base_url, model, temperature, is_active)
                    VALUES (?, NULL, NULL, 0.7, 0)
                    """,
                    (provider,),
                )

        # 若没有激活项，则优先使用环境变量/默认配置
        cursor.execute("SELECT provider FROM llm_config WHERE is_active = 1 LIMIT 1")
        if cursor.fetchone() is None:
            default_provider = getattr(settings, "DEFAULT_LLM_PROVIDER", "demo") or "demo"
            cursor.execute("UPDATE llm_config SET is_active = 0")
            cursor.execute("UPDATE llm_config SET is_active = 1 WHERE provider = ?", (default_provider,))

        conn.commit()
        conn.close()
    
    def get_provider(self, provider_name: str) -> LLMProviderBase:
        """获取LLM提供商实例"""
        return self.providers.get(provider_name, self.providers['demo'])
    
    def test_connection(self, provider: str, api_key: str, base_url: Optional[str] = None) -> Dict[str, Any]:
        """测试连接"""
        try:
            provider_instance = self.get_provider(provider)
            result = provider_instance.test_connection(api_key, base_url)
            return result
        except Exception as e:
            return {'success': False, 'message': f'测试失败: {str(e)}'}
    
    def list_models(self, provider: str, api_key: str, base_url: Optional[str] = None) -> List[Dict[str, str]]:
        """获取模型列表"""
        try:
            provider_instance = self.get_provider(provider)
            models = provider_instance.list_models(api_key, base_url)
            return models
        except Exception as e:
            return []

    def get_active_provider(self) -> str:
        """获取当前激活的提供商（持久化在DB）"""
        try:
            from ... import persist

            cfg = persist.load_runtime_config() or {}
            if cfg.get("provider"):
                return str(cfg["provider"])
        except Exception:
            pass
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute("SELECT provider FROM llm_config WHERE is_active = 1 LIMIT 1")
            row = cursor.fetchone()
            conn.close()
            if row and row[0]:
                return row[0]
        except Exception:
            pass
        return getattr(settings, "DEFAULT_LLM_PROVIDER", "demo") or "demo"

    def set_active_provider(self, provider: str) -> bool:
        """设置激活提供商（写入DB）"""
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute("UPDATE llm_config SET is_active = 0")
            cursor.execute("UPDATE llm_config SET is_active = 1 WHERE provider = ?", (provider,))
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False

    def _resolve_runtime_config(
        self,
        provider: Optional[str],
        api_key: Optional[str],
        base_url: Optional[str],
        model: Optional[str],
        temperature: Optional[float],
    ) -> Dict[str, Any]:
        """把调用入参和DB配置合并成运行时配置"""
        effective_provider = provider or self.get_active_provider()
        cfg = self.get_config(effective_provider) or {}
        return {
            "provider": effective_provider,
            "api_key": api_key if api_key is not None else cfg.get("api_key"),
            "base_url": base_url if base_url is not None else cfg.get("base_url"),
            "model": model if model is not None else cfg.get("model"),
            "temperature": temperature if temperature is not None else cfg.get("temperature", 0.7),
        }
    
    def chat_completions(
        self,
        prompt: str,
        history: List[Dict],
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
    ) -> str:
        """对话生成"""
        import time as _time
        last_error = None
        try:
            runtime = self._resolve_runtime_config(provider, api_key, base_url, model, temperature)
            provider_instance = self.get_provider(runtime["provider"])

            # 数据流向守卫：PPT / 课件 / 动画 / 游戏生成全走本方法，
            # 不插桩等于主生成链路完全裸奔。必须在发起请求之前。
            _flow = _guard(
                prompt=prompt, history=history or [],
                base_url=runtime.get("base_url") or "",
                provider=runtime["provider"],
            )
            if not _flow.get("allowed", True):
                from ...core.errors import DataEgressBlockedError

                raise DataEgressBlockedError(
                    _flow.get("reason") or "敏感数据外发被阻断"
                )
            if _flow.get("action") == "redact":
                prompt = _redact_text(prompt)
                history = _redact_history(history)
            # 尝试调用，失败自动重试2次（共3次），重试之间增加延迟
            for i in range(3):
                try:
                    result = provider_instance.chat_completions(
                        prompt,
                        history,
                        runtime["temperature"],
                        runtime["api_key"],
                        runtime["base_url"],
                        runtime["model"],
                    )
                    # 检查结果是否是错误消息（某些provider不抛异常而是返回错误字符串）
                    if isinstance(result, str) and result.startswith("生成失败:"):
                        raise Exception(result)
                    return result
                except Exception as e:
                    last_error = str(e)
                    if i < 1:  # 减少重试次数为1次
                        wait = 2  # 缩短等待时间为2秒
                        print(f"[LLM] 第{i+1}次调用失败 ({last_error[:100]})，{wait}s后重试...")
                        _time.sleep(wait)
                    continue
            # 不再静默降级到 demo 编造内容：真实模型调用失败必须如实暴露
            raise LLMUnavailableError(
                f"LLM 调用失败（已重试仍不可用）：{last_error}"
            )
        except LLMUnavailableError:
            raise
        except DataEgressBlockedError:
            # 合规阻断必须原样透传：包成 LLMUnavailableError 会让它退化成
            # "调用失败"，用户看不出这是策略拦截、也不知道该怎么处理。
            raise
        except Exception as e:
            # 配置/初始化异常同样如实暴露，禁止返回假数据
            raise LLMUnavailableError(f"LLM 服务异常：{e}") from e
    
    def get_embeddings(
        self,
        text: str,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> List[float]:
        """获取文本嵌入"""
        try:
            runtime = self._resolve_runtime_config(provider, api_key, base_url, model, None)
            provider_instance = self.get_provider(runtime["provider"])
            return provider_instance.get_embeddings(text, runtime["api_key"], runtime["base_url"], runtime["model"])
        except Exception as e:
            # embedding 失败必须显式暴露，返回全零向量会静默污染检索结果（隐性造假）
            raise LLMUnavailableError(f"embedding 失败：{e}") from e
    
    def stream_chat_completions(
        self,
        prompt: str,
        history: List[Dict],
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
    ) -> Generator[str, None, None]:
        """流式对话生成"""
        try:
            runtime = self._resolve_runtime_config(provider, api_key, base_url, model, temperature)
            provider_instance = self.get_provider(runtime["provider"])

            # 数据流向守卫：命中阻断时只产出提示，绝不发出请求 ——
            # 这里是生成器，抛异常会让 SSE 流被截断，前端只看到连接中断。
            _flow = _guard(
                prompt=prompt, history=history or [],
                base_url=runtime.get("base_url") or "",
                provider=runtime["provider"],
            )
            if not _flow.get("allowed", True):
                yield _guard_notice(_flow)
                return
            if _flow.get("action") == "redact":
                prompt = _redact_text(prompt)
                history = _redact_history(history)
            # 尝试调用，失败自动重试2次
            for i in range(3):
                try:
                    for chunk in provider_instance.stream_chat_completions(
                        prompt=prompt,
                        history=history,
                        temperature=runtime["temperature"],
                        api_key=runtime["api_key"],
                        base_url=runtime["base_url"],
                        model=runtime["model"]
                    ):
                        yield chunk
                    return
                except Exception as e:
                    if i == 2:
                        # 最后一次失败，使用演示模式兜底
                        demo_provider = self.get_provider('demo')
                        for chunk in demo_provider.stream_chat_completions(
                            prompt=prompt,
                            history=history,
                            temperature=runtime["temperature"]
                        ):
                            yield chunk
                        return
                    continue
        except Exception as e:
            # 兜底到演示模式
            demo_provider = self.get_provider('demo')
            for chunk in demo_provider.stream_chat_completions(
                prompt=prompt,
                history=history,
                temperature=temperature or 0.7
            ):
                yield chunk
    
    def stream_vision_chat(
        self,
        prompt: str,
        image_base64: str,
        history: List[Dict] = None,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
    ) -> Generator[str, None, None]:
        """视觉识图流式对话 - 自动路由到对应供应商的视觉API"""
        if history is None:
            history = []
        try:
            runtime = self._resolve_runtime_config(provider, api_key, base_url, model, temperature)
            provider_name = runtime["provider"]

            # DashScope(通义千问)使用专用 MultiModalConversation API
            if provider_name == "dashscope":
                provider_instance = self.get_provider("dashscope")
                if hasattr(provider_instance, 'stream_vision_chat'):
                    for chunk in provider_instance.stream_vision_chat(
                        prompt=prompt,
                        image_base64=image_base64,
                        history=history,
                        temperature=runtime["temperature"],
                        api_key=runtime["api_key"],
                        base_url=runtime["base_url"],
                        model=runtime.get("model") or "qwen-vl-plus",
                    ):
                        yield chunk
                    return

            # 其他供应商使用OpenAI兼容格式
            from openai import OpenAI
            client = OpenAI(
                api_key=runtime["api_key"],
                base_url=runtime["base_url"]
            )
            
            # 构建消息
            messages = []
            for item in (history or []):
                if item.get('role') in ('user', 'assistant'):
                    messages.append({'role': item['role'], 'content': item.get('content', '')})
            
            # 添加多模态消息
            messages.append({
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': prompt},
                    {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{image_base64}'}}
                ]
            })
            
            # 自动选择支持视觉的模型
            vision_model = runtime.get("model") or "gpt-4o"
            
            stream = client.chat.completions.create(
                model=vision_model,
                messages=messages,
                temperature=runtime["temperature"],
                max_tokens=2048,
                stream=True
            )
            
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            # 兜底：当不支持视觉时，给出友好提示并用纯文本模式回答
            yield f"⚠️ 当前模型不支持图片识别（{str(e)[:100]}），正在用文本模式分析...\n\n"
            fallback_prompt = f"用户上传了一张图片并问：{prompt}\n\n由于当前模型不支持图片识别，请告知用户需要配置支持视觉的模型（如 GPT-4o、Qwen-VL、GLM-4V 等）才能识别图片内容。同时尝试根据用户的文字描述给出有用的回答。"
            try:
                for chunk in self.stream_chat_completions(
                    prompt=fallback_prompt,
                    history=history or [],
                    provider=provider
                ):
                    yield chunk
            except Exception:
                yield "请配置支持视觉功能的模型（如 GPT-4o、Qwen-VL、GLM-4V 等）以使用图片识别功能。"

    def save_config(self, provider: str, api_key: Optional[str] = None, base_url: Optional[str] = None,
                   model: Optional[str] = None, temperature: float = 0.7, is_active: bool = False) -> bool:
        """保存配置"""
        try:
            self._last_db_error = None
            # 加密API Key
            encrypted_key = crypto_utils.encrypt(api_key) if api_key else None
            
            conn = self._connect()
            cursor = conn.cursor()
            
            # 检查是否已有配置
            cursor.execute('SELECT id FROM llm_config WHERE provider = ?', (provider,))
            existing = cursor.fetchone()
            
            if existing:
                # 更新配置
                cursor.execute(
                    f"""
                    UPDATE llm_config
                    SET {self._api_key_col} = ?, base_url = ?, model = ?, temperature = ?
                    WHERE provider = ?
                    """,
                    (encrypted_key, base_url, model, temperature, provider),
                )
            else:
                # 插入新配置
                cursor.execute(
                    f"""
                    INSERT INTO llm_config (provider, {self._api_key_col}, base_url, model, temperature, is_active)
                    VALUES (?, ?, ?, ?, ?, 0)
                    """,
                    (provider, encrypted_key, base_url, model, temperature),
                )

            if is_active:
                cursor.execute("UPDATE llm_config SET is_active = 0")
                cursor.execute("UPDATE llm_config SET is_active = 1 WHERE provider = ?", (provider,))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            self._last_db_error = str(e)
            # 不吞异常：打印到控制台，便于排查
            try:
                print(f"[LLMConfig] save_config failed: {e}")
            except Exception:
                pass
            return False
    
    def get_config(self, provider: str) -> Dict[str, Any]:
        """获取配置"""
        try:
            from ... import persist

            pe = persist.get_provider_runtime(provider)
            cfg = persist.load_runtime_config() or {}
            keys = cfg.get("apiKeys") or {}
            if keys or cfg.get("provider"):
                return {
                    "api_key": pe["api_key"],
                    "base_url": pe["base_url"],
                    "model": pe["model"],
                    "temperature": pe["temperature"],
                    "is_active": pe["is_active"],
                }
        except Exception:
            pass
        try:
            conn = self._connect()
            cursor = conn.cursor()
            
            cursor.execute(
                f"""
                SELECT {self._api_key_col}, base_url, model, temperature, is_active
                FROM llm_config
                WHERE provider = ?
                """,
                (provider,),
            )
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                # 解密API Key
                api_key = crypto_utils.decrypt(result[0]) if result[0] else None
                return {
                    'api_key': api_key,
                    'base_url': result[1],
                    'model': result[2],
                    'temperature': result[3],
                    'is_active': bool(result[4]),
                }
            return {}
        except Exception as e:
            return {}
    
    def get_all_configs(self) -> Dict[str, Dict[str, Any]]:
        """获取所有配置"""
        try:
            conn = self._connect()
            cursor = conn.cursor()
            
            cursor.execute(
                f"SELECT provider, {self._api_key_col}, base_url, model, temperature, is_active FROM llm_config"
            )
            results = cursor.fetchall()
            conn.close()
            
            configs = {}
            for row in results:
                provider = row[0]
                api_key = crypto_utils.decrypt(row[1]) if row[1] else None
                configs[provider] = {
                    'api_key': api_key,
                    'base_url': row[2],
                    'model': row[3],
                    'temperature': row[4],
                    'is_active': bool(row[5]),
                }
            return configs
        except Exception as e:
            return {}

    def get_last_db_error(self) -> Optional[str]:
        """获取最近一次数据库错误信息（用于接口返回更友好的提示）"""
        return self._last_db_error

# 全局单例实例
llm_service = LLMService()