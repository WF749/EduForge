"""系统与可观测性接口：厂商元数据、实时模型、运行指标。"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Body, Query
from fastapi.responses import JSONResponse

from ..core.errors import ErrorCode
from ..core.logging_setup import get_logger
from ..core.observability import metrics
from ..core.providers import (
    build_auth_headers,
    get_provider,
    models_endpoint,
    provider_payload,
    resolve_base_url,
)
from ..persist import get_active_llm_settings

log = get_logger("api.system")
router = APIRouter()


@router.get("/providers")
def list_providers():
    """厂商元数据（不含任何密钥）。前端设置页据此渲染厂商与能力。"""
    return {"success": True, "providers": provider_payload()}


@router.get("/models/live")
async def live_models(provider: str = Query("dashscope"), api_key: Optional[str] = None):
    """用用户自己的 Key 向厂商拉取**实时**模型列表。

    这是避免"硬编码模型名过时"的根本手段 —— 权威答案由厂商给出，
    不依赖本项目维护者的知识截止日期。
    """
    spec = get_provider(provider)
    if spec.protocol in ("demo",):
        return {"success": True, "source": "static", "models": [], "note": "演示模式无需选择模型"}

    cfg = get_active_llm_settings()
    key = (api_key or "").strip() or (cfg.get("api_key") or "")
    base_url = resolve_base_url(provider, cfg.get("base_url"))

    if not key and spec.protocol != "local":
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "code": ErrorCode.NO_API_KEY,
                "message": f"请先为 {spec.label} 配置 API Key",
                "hint": "填写并保存后即可拉取该厂商的模型列表。",
            },
        )

    url = models_endpoint(provider, cfg.get("base_url"))
    if not url:
        return {"success": False, "code": ErrorCode.BAD_BASE_URL, "message": "无法构造模型列表地址"}

    try:
        async with httpx.AsyncClient(timeout=25.0, verify=False) as client:
            resp = await client.get(url, headers=build_auth_headers(provider, key))
            if resp.status_code >= 400:
                from ..core.errors import _map_http_error
                err = _map_http_error(resp.status_code, resp.text, provider, "models")
                return JSONResponse(
                    status_code=getattr(err, "status", 400),
                    content={"success": False, "code": getattr(err, "code", "E1003"),
                             "message": str(err), "hint": getattr(err, "hint", "")},
                )
            data = resp.json()
    except Exception as e:
        return JSONResponse(
            status_code=502,
            content={"success": False, "code": ErrorCode.BAD_BASE_URL,
                     "message": f"无法连接 {spec.label}：{e}"},
        )

    raw = data.get("data") if isinstance(data, dict) else data
    models: List[Dict[str, Any]] = []
    for m in (raw or []):
        if isinstance(m, dict):
            name = m.get("id") or m.get("name") or m.get("model")
            if name:
                models.append({
                    "name": name,
                    "description": m.get("description", "厂商实时返回"),
                    "price_info": "以厂商控制台为准",
                })
        elif isinstance(m, str):
            models.append({"name": m, "description": "厂商实时返回", "price_info": "以厂商控制台为准"})

    return {"success": True, "source": "live", "count": len(models), "models": models}


@router.get("/metrics")
def get_metrics(window: Optional[int] = Query(None, description="统计窗口秒数，默认全量"),
                recent: int = Query(0, description="返回最近 N 条明细")):
    """可观测性：LLM/工具/Agent/请求的调用次数、成功率、P95 延迟、token 与成本。"""
    out: Dict[str, Any] = {"success": True, "summary": metrics.summary(window)}
    if recent > 0:
        out["recent"] = metrics.recent(limit=min(recent, 200))
    return JSONResponse(out)


@router.get("/metrics/events")
def get_events(kind: Optional[str] = Query(None), limit: int = Query(100)):
    """按类型查看调用明细（llm / tool / agent / request）。"""
    return {"success": True, "events": metrics.recent(limit=min(limit, 500), kind=kind)}
