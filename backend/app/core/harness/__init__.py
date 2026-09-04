"""EduForge LLM Harness —— 企业级大模型调用层。

核心理念：让 Agent 跑得稳、看得见、管得住。
  - 统一接口（BaseLLMClient）
  - 横切能力（重试 / 超时 / 熔断 / 全链路追踪）
  - 降级必须显式标记（degraded=True），彻底禁止静默造假
"""

from .base import BaseLLMClient, WrappedProvider
from .circuit_breaker import CircuitBreaker
from .exceptions import (
    LLMError,
    LLMProviderError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from .manager import LLMManager
from .models import ChatMessage, EmbeddingResult, LLMResponse
from .retry import with_retry
from .tracing import TraceCollector

__all__ = [
    "BaseLLMClient",
    "WrappedProvider",
    "CircuitBreaker",
    "LLMError",
    "LLMProviderError",
    "LLMTimeoutError",
    "LLMUnavailableError",
    "LLMManager",
    "ChatMessage",
    "EmbeddingResult",
    "LLMResponse",
    "with_retry",
    "TraceCollector",
]
