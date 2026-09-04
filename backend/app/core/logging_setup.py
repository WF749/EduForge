"""结构化日志与请求上下文（request_id / trace_id）。

要求：任何一条日志都能回答"这是哪次请求、哪个用户会话、哪个 Agent、哪一步"。
"""

from __future__ import annotations

import contextvars
import json
import logging
import logging.handlers
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

# ---- 请求上下文（并发安全） ------------------------------------------------

_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
_trace_id: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="-")
_session_id: contextvars.ContextVar[str] = contextvars.ContextVar("session_id", default="-")
_agent_name: contextvars.ContextVar[str] = contextvars.ContextVar("agent_name", default="-")
_step_name: contextvars.ContextVar[str] = contextvars.ContextVar("step_name", default="-")


def set_context(**kwargs: Optional[str]) -> None:
    mapping = {
        "request_id": _request_id,
        "trace_id": _trace_id,
        "session_id": _session_id,
        "agent_name": _agent_name,
        "step_name": _step_name,
    }
    for k, v in kwargs.items():
        if k in mapping and v is not None:
            mapping[k].set(str(v))


def current_context() -> Dict[str, str]:
    return {
        "request_id": _request_id.get(),
        "trace_id": _trace_id.get(),
        "session_id": _session_id.get(),
        "agent": _agent_name.get(),
        "step": _step_name.get(),
    }


def new_trace_id() -> str:
    import uuid
    return uuid.uuid4().hex[:16]


# ---- 结构化格式化器 --------------------------------------------------------

class JsonFormatter(logging.Formatter):
    """输出单行 JSON，便于日志采集（ELK / Loki / 阿里云 SLS）。"""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        payload.update(current_context())
        # 附加业务字段：log.info("x", extra={"tokens": 100})
        for key, val in record.__dict__.items():
            if key.startswith("ctx_"):
                payload[key[4:]] = val
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """控制台可读格式，带上下文。"""

    def format(self, record: logging.LogRecord) -> str:
        ctx = current_context()
        base = (
            f"{time.strftime('%H:%M:%S', time.localtime(record.created))} "
            f"{record.levelname:<5} [{ctx['request_id'][:8]}|{ctx['agent']:<10}] "
            f"{record.getMessage()}"
        )
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


_configured = False


def setup_logging(level: str = "INFO", log_dir: Optional[Path] = None, json_file: bool = True) -> None:
    """初始化日志。重复调用安全。"""
    global _configured
    if _configured:
        return
    _configured = True

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    for h in list(root.handlers):
        root.removeHandler(h)

    # 控制台
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(TextFormatter())
    root.addHandler(console)

    # 文件（JSON，便于检索）
    if log_dir and json_file:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            fh = logging.handlers.RotatingFileHandler(
                log_dir / "app.jsonl", maxBytes=20 * 1024 * 1024, backupCount=5, encoding="utf-8"
            )
            fh.setFormatter(JsonFormatter())
            fh.setLevel(logging.INFO)
            root.addHandler(fh)
        except Exception as e:  # 日志失败不能拖垮主程序
            print(f"[logging] 文件日志初始化失败: {e}")

    # 压制第三方噪声
    for noisy in ("httpx", "httpcore", "urllib3", "chromadb", "sentence_transformers", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
