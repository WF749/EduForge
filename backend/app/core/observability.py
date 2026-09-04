"""可观测性：全链路调用指标采集。

设计目标（对应"不能靠主观感受判断效果"）
----------------------------------------
每一次 LLM 调用 / 工具调用 / Agent 运行都会落一条**结构化指标**，可回答：
  - 这次请求用了哪个 Agent、哪个模型、调用了哪些工具？
  - 每一步耗时多少、成功还是失败、失败原因是什么？
  - 总共消耗多少 token、约多少成本？
  - 成功率 / P95 延迟是多少？

指标先写内存环形缓冲（供 /api/metrics 实时查看），同时落 JSONL 文件（供离线分析）。
后续可无缝替换为 Prometheus / OTLP 导出。
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

from .logging_setup import current_context, get_logger

log = get_logger("metrics")

_MAX_EVENTS = 2000           # 环形缓冲上限
_METRICS_FILE = "metrics.jsonl"


@dataclass
class Span:
    """一次调用的完整记录。"""

    kind: str                       # llm | tool | agent | request
    name: str                       # 模型名 / 工具名 / Agent 名
    start: float = field(default_factory=time.time)
    end: Optional[float] = None
    duration_ms: float = 0.0
    status: str = "running"         # ok | error | degraded | running
    error_code: str = ""
    error_message: str = ""
    # LLM 相关
    provider: str = ""
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_cny: float = 0.0
    # 其他
    attempt: int = 1                # 第几次尝试（>1 表示发生过重试）
    degraded: bool = False
    meta: Dict[str, Any] = field(default_factory=dict)
    ctx: Dict[str, str] = field(default_factory=dict)

    def finish(self, status: str = "ok", error: Optional[BaseException] = None, **kw) -> "Span":
        self.end = time.time()
        self.duration_ms = round((self.end - self.start) * 1000, 2)
        self.status = status
        if error is not None:
            self.status = "error"
            self.error_message = f"{type(error).__name__}: {error}"
            self.error_code = getattr(error, "code", "")
        for k, v in kw.items():
            if hasattr(self, k):
                setattr(self, k, v)
        self.ctx = current_context()
        return self

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MetricsCollector:
    """线程安全的指标采集器。"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._events: Deque[Span] = deque(maxlen=_MAX_EVENTS)
        self._file: Optional[Path] = None

    def configure(self, log_dir: Optional[Path]) -> None:
        if not log_dir:
            return
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            self._file = log_dir / _METRICS_FILE
        except Exception as e:
            log.warning("指标文件初始化失败: %s", e)

    def record(self, span: Span) -> Span:
        with self._lock:
            self._events.append(span)
            if self._file:
                try:
                    import json
                    with self._file.open("a", encoding="utf-8") as f:
                        f.write(json.dumps(span.to_dict(), ensure_ascii=False) + "\n")
                except Exception:
                    pass  # 指标落盘失败绝不干扰主流程
        log.debug("%s %s %s %.0fms", span.kind, span.name, span.status, span.duration_ms)
        return span

    # ---- 聚合查询 ---------------------------------------------------------

    def summary(self, window: Optional[int] = None) -> Dict[str, Any]:
        """输出聚合指标。window=None 表示全量。"""
        with self._lock:
            events: List[Span] = list(self._events)
        if window:
            events = [e for e in events if time.time() - e.start <= window]

        def _agg(kind: str) -> Dict[str, Any]:
            items = [e for e in events if e.kind == kind]
            if not items:
                return {"count": 0}
            ok = [e for e in items if e.status == "ok"]
            errs = [e for e in items if e.status == "error"]
            durs = sorted(e.duration_ms for e in items)
            p95 = durs[int(len(durs) * 0.95) - 1] if len(durs) > 1 else (durs[0] if durs else 0)
            return {
                "count": len(items),
                "success": len(ok),
                "error": len(errs),
                "success_rate": round(len(ok) / len(items), 4),
                "avg_ms": round(sum(durs) / len(durs), 2),
                "p95_ms": round(p95, 2),
                "max_ms": round(max(durs), 2),
            }

        llm_events = [e for e in events if e.kind == "llm"]
        by_model: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "tokens": 0, "cost_cny": 0.0, "errors": 0})
        for e in llm_events:
            b = by_model[f"{e.provider}/{e.model}"]
            b["count"] += 1
            b["tokens"] += e.total_tokens
            b["cost_cny"] = round(b["cost_cny"] + e.cost_cny, 6)
            if e.status == "error":
                b["errors"] += 1

        tool_events = [e for e in events if e.kind == "tool"]
        by_tool: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "errors": 0, "avg_ms": 0.0})
        for name in {e.name for e in tool_events}:
            items = [e for e in tool_events if e.name == name]
            by_tool[name] = {
                "count": len(items),
                "errors": len([e for e in items if e.status == "error"]),
                "avg_ms": round(sum(e.duration_ms for e in items) / len(items), 2),
                "success_rate": round(len([e for e in items if e.status == "ok"]) / len(items), 4),
            }

        retries = len([e for e in events if e.attempt > 1])

        return {
            "window_seconds": window,
            "total_events": len(events),
            "llm": _agg("llm"),
            "tool": _agg("tool"),
            "agent": _agg("agent"),
            "request": _agg("request"),
            "retries": retries,
            "by_model": dict(by_model),
            "by_tool": dict(by_tool),
            "total_tokens": sum(e.total_tokens for e in llm_events),
            "total_cost_cny": round(sum(e.cost_cny for e in llm_events), 6),
        }

    def recent(self, limit: int = 100, kind: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            events = [e for e in self._events if kind is None or e.kind == kind]
        return [e.to_dict() for e in list(events)[-limit:]]


# ---- 成本估算（元 / 百万 token，人民币；仅量级参考） ------------------------

_PRICE_CNY_PER_M = {
    "dashscope/qwen-plus": (0.8, 2.0),
    "dashscope/qwen-flash": (0.3, 1.5),
    "dashscope/qwen-turbo": (0.3, 0.6),
    "dashscope/qwen3-max": (20.0, 60.0),
    "dashscope/deepseek-v4-flash": (1.0, 4.0),
    "dashscope/deepseek-v4-pro": (3.0, 12.0),
    "deepseek/deepseek-v4-flash": (1.0, 4.0),
    "deepseek/deepseek-v4-pro": (3.0, 12.0),
    "openai/gpt-4o-mini": (1.1, 4.4),
    "zhipu/glm-4-flash": (0.0, 0.0),
    "moonshot/moonshot-v1-8k": (0.0, 0.0),
}


def estimate_cost_cny(provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """按模型估算成本（元）。未收录的模型返回 0，不臆造数字。"""
    key = f"{provider}/{model}".lower()
    price = _PRICE_CNY_PER_M.get(key)
    if not price:
        return 0.0
    pin, pout = price
    return round(prompt_tokens / 1_000_000 * pin + completion_tokens / 1_000_000 * pout, 6)


metrics = MetricsCollector()


# ---- 便捷入口 -------------------------------------------------------------

class span_scope:
    """上下文管理器：自动计时、记录成功/失败。

    with span_scope("llm", model, provider=..., model=...) as s:
        ...
        s.total_tokens = 123
    """

    def __init__(self, kind: str, name: str, **fields):
        self.span = Span(kind=kind, name=name, **fields)
        self._error: Optional[BaseException] = None

    def __enter__(self) -> Span:
        return self.span

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc is not None:
            self.span.finish("error", error=exc)
        else:
            self.span.finish(self.span.status if self.span.status != "running" else "ok")
        metrics.record(self.span)
        return False  # 不吞异常
