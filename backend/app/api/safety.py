"""数据合规接口：把"这次生成的数据去了哪"变成可查询、可预检的能力。

两个端点
--------
  GET  /api/safety/status   当前策略与出校目标，供设置页/状态栏展示
  POST /api/safety/scan     预检：给定文本，返回定级与路由决策，**不调用任何模型**

为什么需要预检（scan）
----------------------
阻断只能发生在调用前，但教师需要的是"我还没点生成，就知道这段内容能不能发"。
scan 让前端在提交前把「课题 / 要求 / 自定义内容」送进来做本地判别，
命中敏感项时先提示，而不是等生成失败再解释原因 —— 后者体验上是"系统不让我用"，
前者才是"系统在保护我"。

scan 全程本地执行（正则 + 结构规则），不产生任何外网请求。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body
from pydantic import BaseModel, Field

from ..core.providers import get_provider, resolve_base_url
from ..persist import get_active_llm_settings
from ..safety import (
    LEVELS,
    SAFETY_MODES,
    classify,
    decide,
    get_safety_mode,
    is_private_endpoint,
    redact,
)

log = None  # 模块级 logger 按需创建，避免导入期副作用
router = APIRouter()

# 各级别的人话解释，直接给前端展示用
LEVEL_LABELS = {
    "L1": "公开数据",
    "L2": "校内一般教学数据",
    "L3": "敏感数据（含个人身份标识）",
    "L4": "重要数据（未成年人敏感个人信息）",
    "L5": "核心数据",
}


def _target() -> Dict[str, Any]:
    """解析当前生效的模型地址，判断它是否在校内。"""
    cfg = get_active_llm_settings()
    prov = cfg.get("provider") or "demo"
    try:
        spec = get_provider(prov)
        protocol = spec.protocol
        label = spec.label
    except Exception:  # noqa: BLE001
        protocol, label = "openai", prov
    base_url = resolve_base_url(prov, cfg.get("base_url"))
    return {
        "provider": prov,
        "provider_label": label,
        "protocol": protocol,
        "base_url": base_url,
        "private": is_private_endpoint(base_url),
    }


@router.get("/safety/status")
def safety_status():
    """当前合规策略：模式、阻断级别、目标是否出校。"""
    t = _target()
    mode = get_safety_mode()
    return {
        "success": True,
        "mode": mode,
        "modes": list(SAFETY_MODES),
        "levels": list(LEVELS),
        "level_labels": LEVEL_LABELS,
        "block_level": "L3",
        "target": t,
        "egress": not t["private"],
        "note": (
            "当前会发往公网厂商，命中 L3 及以上将按策略处理"
            if not t["private"] else
            "当前目标为校内/本机推理服务，数据未出校"
        ),
    }


class ScanRequest(BaseModel):
    text: str = Field("", description="待检内容（课题、要求、自定义文本）")
    system: str = Field("", description="系统提示词，可为空")
    history: List[Dict[str, str]] = Field(default_factory=list)
    preview_redact: bool = Field(False, description="是否同时返回脱敏后的文本")


@router.post("/safety/scan")
def safety_scan(req: ScanRequest = Body(...)):
    """本地预检：定级 + 路由决策 + 可选脱敏预览。全程不联网、不调用模型。"""
    t = _target()
    clf = classify(req.system, "\n".join(
        str(h.get("content") or "") for h in (req.history or [])
    ), req.text)
    decision = decide(t["base_url"], clf, protocol=t["protocol"])

    out: Dict[str, Any] = {
        "success": True,
        "level": clf.level,
        "level_label": LEVEL_LABELS.get(clf.level, clf.level),
        "is_sensitive": clf.is_sensitive,
        "findings": [f.to_dict() for f in clf.findings],
        "route": decision.route,
        "egress": decision.egress,
        "action": decision.action,
        "allowed": decision.allowed,
        "reason": decision.reason,
        "target": t,
        "mode": get_safety_mode(),
    }

    if req.preview_redact and clf.findings:
        masked, n = redact(req.text)
        out["redacted_text"] = masked
        out["redacted_count"] = n

    return out
