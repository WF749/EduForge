"""HTTP 中间件：请求身份、耗时、访问日志。"""

from __future__ import annotations

import time
import uuid

from fastapi import FastAPI, Request

from .logging_setup import get_logger, new_trace_id, set_context
from .observability import Span, metrics

log = get_logger("access")


def install_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        # 复用上游传入的 trace_id（便于跨服务串联），否则新建
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        tid = request.headers.get("x-trace-id") or new_trace_id()
        sid = request.headers.get("x-session-id") or request.query_params.get("session_id") or "-"
        set_context(
            request_id=rid, trace_id=tid, session_id=sid,
            agent_name="http", step_name=request.url.path,
        )

        # 数据流向槽位：端点里写入的决策，请求结束时要回写到响应头。
        # 必须在 call_next 之前建好，子 task 才能继承到同一个 dict 对象。
        try:
            from .llm_gateway import new_data_flow_slot

            flow_slot = new_data_flow_slot()
        except Exception:  # noqa: BLE001
            flow_slot = None

        start = time.time()
        span = Span(kind="request", name=f"{request.method} {request.url.path}")
        status_code = 500
        error = None
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            error = e
            raise
        finally:
            elapsed = (time.time() - start) * 1000
            span.status = "ok" if status_code < 400 else "error"
            if error is not None:
                span.error_message = f"{type(error).__name__}: {error}"
            elif status_code >= 400 and not span.error_message:
                span.error_message = f"HTTP {status_code}"
            span.meta["status_code"] = status_code
            span.finish(span.status)
            metrics.record(span)
            log.info("%s %s -> %d (%.0fms)", request.method, request.url.path, status_code, elapsed)

        response.headers["x-request-id"] = rid
        response.headers["x-trace-id"] = tid
        response.headers["x-response-time-ms"] = f"{elapsed:.0f}"

        # 数据流向：让"这次生成的数据去了哪"在每一次响应里都可查。
        # 这是"数据不出校"从口号变成可验证结论的关键 —— 管理员打开 F12 就能看到。
        if flow_slot:
            response.headers["X-Data-Level"] = str(flow_slot.get("level") or "")
            response.headers["X-Data-Route"] = str(flow_slot.get("route") or "")
            response.headers["X-Data-Action"] = str(flow_slot.get("action") or "")
            response.headers["X-Egress"] = "true" if flow_slot.get("egress") else "false"
            findings = flow_slot.get("findings") or []
            if findings:
                # 只放类型与数量，绝不放原文 —— 响应头本身也可能被日志采集
                response.headers["X-Data-Findings"] = ",".join(
                    f"{f.get('kind')}x{f.get('count')}" for f in findings
                )
        return response
