"""全链路追踪（轻量内存实现，可替换为 OpenTelemetry）。

目标：每一次 LLM 调用都可被追溯——谁、用哪个模型、耗时多少、成功还是降级、
错误原因是什么。企业级系统必须"看得见"，否则无法排障与审计。
"""

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TraceSpan:
    trace_id: str
    name: str
    provider: Optional[str]
    model: Optional[str]
    started_at: float
    ended_at: Optional[float] = None
    latency_ms: float = 0.0
    status: str = "pending"  # pending | ok | error | degraded
    error: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)


class TraceCollector:
    _store: Dict[str, TraceSpan] = {}
    _lock = threading.Lock()
    _max_retain = 200

    @classmethod
    def start(cls, name: str, provider: Optional[str] = None, model: Optional[str] = None) -> str:
        trace_id = uuid.uuid4().hex[:16]
        span = TraceSpan(
            trace_id=trace_id,
            name=name,
            provider=provider,
            model=model,
            started_at=time.time(),
        )
        with cls._lock:
            cls._store[trace_id] = span
        return trace_id

    @classmethod
    def finish(
        cls,
        trace_id: str,
        status: str = "ok",
        error: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        with cls._lock:
            span = cls._store.get(trace_id)
            if span:
                span.ended_at = time.time()
                span.latency_ms = (span.ended_at - span.started_at) * 1000
                span.status = status
                span.error = error
                if meta:
                    span.meta.update(meta)
                # 仅保留最近 _max_retain 条，避免内存无限增长
                if len(cls._store) > cls._max_retain:
                    oldest = sorted(cls._store.items(), key=lambda kv: kv[1].started_at)[
                        : cls._max_retain // 4
                    ]
                    for k, _ in oldest:
                        cls._store.pop(k, None)

    @classmethod
    def get(cls, trace_id: str) -> Optional[TraceSpan]:
        with cls._lock:
            return cls._store.get(trace_id)

    @classmethod
    def recent(cls, n: int = 50) -> List[TraceSpan]:
        with cls._lock:
            return sorted(cls._store.values(), key=lambda s: s.started_at, reverse=True)[:n]
