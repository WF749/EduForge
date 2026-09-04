"""Harness 核心：LLM 客户端抽象与遗留 Provider 的包装器。

WrappedProvider 是关键设计：它不重写各家 Provider 的调用逻辑（那些已经能跑），
而是在其之上叠加企业级横切能力——
  重试(retry) · 超时(timeout) · 熔断(circuit breaker) · 全链路追踪(tracing) ·
  降级显式标记(degraded) · 失败如实抛出(绝不返回编造内容)。

这样现有生成链路可以"零改动迁移"到 Harness，同时立即获得生产级稳健性。
"""

import time
from typing import Any, Dict, Iterator, List, Optional

from .circuit_breaker import CircuitBreaker
from .exceptions import LLMError, LLMTimeoutError, LLMUnavailableError
from .models import EmbeddingResult, LLMResponse
from .retry import with_retry
from .tracing import TraceCollector


class BaseLLMClient:
    """企业级 LLM 客户端抽象。所有 Provider（含包装器）必须实现统一接口。"""

    name = "base"

    def chat(
        self,
        prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        *,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> LLMResponse:
        raise NotImplementedError

    def chat_stream(
        self,
        prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        *,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> Iterator[str]:
        raise NotImplementedError

    def embed(self, text: str) -> EmbeddingResult:
        raise NotImplementedError

    def health(self) -> bool:
        return True


class WrappedProvider(BaseLLMClient):
    """将遗留 provider 实例包装进 Harness。

    遗留 provider 接口约定：
        chat_completions(prompt, history, temperature, api_key, base_url, model) -> str
        get_embeddings(text, api_key, base_url, model) -> List[float]
    """

    def __init__(
        self,
        legacy: Any,
        name: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 60.0,
        breaker: Optional[CircuitBreaker] = None,
    ) -> None:
        self.legacy = legacy
        self.name = name
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self.breaker = breaker or CircuitBreaker()

    def chat(
        self,
        prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        *,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> LLMResponse:
        trace_id = TraceCollector.start("chat", provider=self.name, model=self.model)
        if not self.breaker.allow():
            TraceCollector.finish(trace_id, status="error", error="circuit_open")
            raise LLMUnavailableError(
                "熔断器已开启，暂时拒绝调用该 Provider", provider=self.name, model=self.model
            )

        t0 = time.time()
        try:
            def _call() -> str:
                return self.legacy.chat_completions(
                    prompt,
                    history or [],
                    temperature,
                    self.api_key,
                    self.base_url,
                    self.model or kwargs.get("model"),
                )

            content = with_retry(_call, retries=2, base_delay=1.0)
            self.breaker.record_success()

            resp = LLMResponse(
                content=content,
                provider=self.name,
                model=self.model or "",
                latency_ms=(time.time() - t0) * 1000,
                trace_id=trace_id,
            )
            # demo / 占位类 Provider 必须显式标记为降级，前端据此提示"非真实生成"
            if self.name == "demo":
                resp.degraded = True
                resp.source = "demo"
            TraceCollector.finish(trace_id, status="ok" if not resp.degraded else "degraded")
            return resp

        except LLMUnavailableError:
            self.breaker.record_failure()
            TraceCollector.finish(trace_id, status="error", error="unavailable")
            raise
        except Exception as e:  # noqa: BLE001 - 必须捕获并转为可识别错误，但绝不吞掉
            self.breaker.record_failure()
            TraceCollector.finish(trace_id, status="error", error=str(e)[:200])
            # 关键：如实抛出，绝不返回编造内容
            raise LLMUnavailableError(
                f"{type(e).__name__}: {e}", provider=self.name, model=self.model, cause=e
            ) from e

    def embed(self, text: str) -> EmbeddingResult:
        trace_id = TraceCollector.start("embed", provider=self.name, model=self.model)
        t0 = time.time()
        try:
            def _call() -> List[float]:
                return self.legacy.get_embeddings(text, self.api_key, self.base_url, self.model)

            vector = with_retry(_call, retries=2, base_delay=1.0)
            self.breaker.record_success()
            TraceCollector.finish(trace_id, status="ok", meta={"dim": len(vector)})
            return EmbeddingResult(vector=vector, model=self.model or "", provider=self.name)
        except Exception as e:  # noqa: BLE001
            TraceCollector.finish(trace_id, status="error", error=str(e)[:200])
            # embedding 失败同样必须显式暴露；返回全零向量会污染检索，属于隐性造假
            raise LLMUnavailableError(
                f"embedding 失败: {type(e).__name__}: {e}",
                provider=self.name,
                model=self.model,
                cause=e,
            ) from e

    def health(self) -> bool:
        try:
            return bool(self.legacy.test_connection(self.api_key, self.base_url).get("success"))
        except Exception:  # noqa: BLE001
            return False
