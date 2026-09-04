"""Agent 能力接口：任务规划、工具执行、结果验证、人机协同。"""

from __future__ import annotations

import asyncio
import json
import queue
import threading
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse, StreamingResponse

from ..agent.context import AgentContext
from ..agent.executor import Executor
from ..agent.orchestrator import Orchestrator
from ..agent.planner import Planner
from ..agent.tools.base import RiskLevel, registry
from ..core.errors import AppError
from ..core.logging_setup import get_logger

log = get_logger("api.agent")
router = APIRouter()


@router.get("/tools")
def list_tools():
    """已注册工具清单（供前端展示 Agent 能力）。"""
    tools = []
    for name in registry.names():
        spec = registry.get(name)
        tools.append({
            "name": name,
            "description": spec.description,
            "category": spec.category,
            "risk": spec.risk.value,
            "requires_approval": spec.risk == RiskLevel.HIGH,
            "requires_llm": spec.requires_llm,
            "timeout_s": spec.timeout_s,
            "parameters": spec.parameters,
        })
    return {"success": True, "count": len(tools), "tools": tools}


@router.post("/plan")
def plan_only(body: Dict[str, Any] = Body(...)):
    """只做任务拆解，不执行。用于前端展示"Agent 打算怎么做"。"""
    goal = (body.get("goal") or body.get("message") or "").strip()
    if not goal:
        return JSONResponse(status_code=422, content={
            "success": False, "code": "E3001", "message": "缺少 goal 参数"})

    ctx = AgentContext(goal=goal, memory=body.get("memory") or {})
    try:
        steps = Planner().plan(goal, ctx)
        return {"success": True, "goal": goal,
                "steps": [s.to_dict() for s in steps]}
    except AppError as e:
        return JSONResponse(status_code=e.status, content=e.to_dict())
    except Exception as e:
        log.exception("任务规划失败")
        return JSONResponse(status_code=500, content={
            "success": False, "code": "E9001", "message": f"规划失败：{e}"})


@router.post("/run")
def run_agent(body: Dict[str, Any] = Body(...)):
    """完整运行一次 Agent（同步返回，适合短任务与调试）。"""
    goal = (body.get("goal") or body.get("message") or "").strip()
    if not goal:
        return JSONResponse(status_code=422, content={
            "success": False, "code": "E3001", "message": "缺少 goal 参数"})

    # 人机协同：默认**不**自动批准高风险操作；
    # 只有请求显式携带 approvals 列表时才放行对应工具。
    approvals = set(body.get("approvals") or [])
    def _approve(name: str, args: Dict[str, Any]) -> bool:
        return name in approvals

    orch = Orchestrator(
        max_steps=int(body.get("max_steps") or 6),
        max_revisions=int(body.get("max_revisions") or 1),
        enable_verification=bool(body.get("verify", True)),
        on_approval_required=_approve,
    )
    try:
        result = orch.run(
            goal,
            session_id=body.get("session_id") or "",
            memory=body.get("memory") or {},
            history=body.get("history") or [],
            content_type=body.get("content_type") or "general",
            grade=body.get("grade") or "",
            subject=body.get("subject") or "",
        )
        return {"success": True, **result.to_dict()}
    except AppError as e:
        return JSONResponse(status_code=e.status, content=e.to_dict())
    except Exception as e:
        log.exception("Agent 运行失败")
        return JSONResponse(status_code=500, content={
            "success": False, "code": "E9001", "message": f"Agent 运行失败：{e}"})


@router.post("/stream")
async def run_agent_stream(body: Dict[str, Any] = Body(...)):
    """流式运行：逐步推送 计划 → 执行进度 → 验证 → 最终答案。

    用 SSE，前端可实时看到 Agent 在做什么，而不是干等。
    """
    goal = (body.get("goal") or body.get("message") or "").strip()
    if not goal:
        return JSONResponse(status_code=422, content={
            "success": False, "code": "E3001", "message": "缺少 goal 参数"})

    approvals = set(body.get("approvals") or [])
    q: "queue.Queue[Dict[str, Any]]" = queue.Queue()
    _SENTINEL = object()

    def _progress(event: str, data: Dict[str, Any]) -> None:
        q.put({"event": event, "data": data})

    def _worker() -> None:
        orch = Orchestrator(
            max_steps=int(body.get("max_steps") or 6),
            max_revisions=int(body.get("max_revisions") or 1),
            enable_verification=bool(body.get("verify", True)),
            on_progress=_progress,
            on_approval_required=lambda n, a: n in approvals,
        )
        try:
            result = orch.run(
                goal,
                session_id=body.get("session_id") or "",
                memory=body.get("memory") or {},
                history=body.get("history") or [],
                content_type=body.get("content_type") or "general",
                grade=body.get("grade") or "",
                subject=body.get("subject") or "",
            )
            q.put({"event": "final", "data": result.to_dict()})
        except Exception as e:
            log.exception("流式 Agent 运行失败")
            q.put({"event": "error", "data": {
                "message": str(e),
                "code": getattr(e, "code", "E9001"),
            }})

    threading.Thread(target=_worker, daemon=True).start()

    async def _gen():
        loop = asyncio.get_event_loop()
        while True:
            item = await loop.run_in_executor(None, q.get)
            yield f"event: {item['event']}\ndata: {json.dumps(item['data'], ensure_ascii=False)}\n\n".encode("utf-8")
            if item["event"] in ("final", "error"):
                break

    return StreamingResponse(_gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})
