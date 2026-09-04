"""Harness 管理器：Provider 注册中心 + 运行时配置解析 + 降级策略执行。

调用方永远只跟 LLMManager 打交道，不直接 new Provider。
"""

from typing import Dict, List, Optional

from .base import BaseLLMClient, WrappedProvider
from .exceptions import LLMUnavailableError
from .models import LLMResponse


class LLMManager:
    def __init__(self) -> None:
        self._clients: Dict[str, BaseLLMClient] = {}
        self._default: Optional[str] = None

    def register(self, name: str, client: BaseLLMClient) -> None:
        self._clients[name] = client
        if self._default is None:
            self._default = name

    def set_default(self, name: str) -> None:
        if name in self._clients:
            self._default = name

    def get(self, name: str) -> Optional[BaseLLMClient]:
        return self._clients.get(name)

    def list_providers(self) -> List[str]:
        return list(self._clients.keys())

    def chat(
        self,
        prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        *,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        name = provider or self._default
        if not name or name not in self._clients:
            raise LLMUnavailableError(f"未找到 Provider: {name}")
        client = self._clients[name]
        # 调用级参数覆盖（不持久化，仅本次生效）
        if isinstance(client, WrappedProvider):
            if api_key:
                client.api_key = api_key
            if base_url:
                client.base_url = base_url
            if model:
                client.model = model
        return client.chat(prompt, history, temperature=temperature)

    def embed(self, text: str, *, provider: Optional[str] = None) -> List[float]:
        name = provider or self._default
        client = self._clients.get(name)  # type: ignore[assignment]
        if client is None:
            raise LLMUnavailableError(f"未找到 Provider: {name}")
        return client.embed(text).vector
