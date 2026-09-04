"""路由决策：这次调用出不出校？出校的话该怎么办？

关键判断：**目标地址是不是校内地址**。

只看厂商名是不够的 —— `local` 协议厂商若被填了公网地址，一样出校；
反过来，任何厂商若 base_url 指向 172.30.x.x，就确实没出校。
因此以**解析后的 base_url 主机**为准，而不是以厂商标签为准。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from ipaddress import ip_address
from typing import List, Optional
from urllib.parse import urlparse

from .classifier import Classification, level_rank

# 策略模式
#   off      完全关闭（不推荐，仅用于排查）
#   warn     只定级与记录，不改变行为 ← 默认
#   sanitize 先本地脱敏再发往云端（保留教学语义，抹掉身份标识）
#   enforce  命中敏感级别且目标在公网时，直接阻断并给出可操作提示
SAFETY_MODES = ("off", "warn", "sanitize", "enforce")

DEFAULT_SAFETY_MODE = "warn"

# 命中该级别即视为"不应出校"
BLOCK_LEVEL = "L3"

# 脱敏解决不了的命中类型。
# 整段试题的教学价值恰恰在题面本身 —— 抹掉题面等于抹掉全部用途。
# 对这类内容套用 sanitize 只会制造"已经安全了"的假象，比直接拦下更危险，
# 因此遇到它们时 sanitize 也必须退化为阻断。
NON_REDACTABLE_KINDS = frozenset({"exam_paper"})

_PRIVATE_HOST_SUFFIX = (".local", ".internal", ".lan")
_PRIVATE_HOSTS = {"localhost"}


def get_safety_mode() -> str:
    """读取当前策略。配置缺失或非法时**退回 warn**而不是 off ——

    配置写错就关闭防护是最危险的失败模式；宁可多告警。
    """
    raw = (os.getenv("EDUFORGE_SAFETY_MODE", "") or "").strip().lower()
    if raw in SAFETY_MODES:
        return raw
    try:
        from ..persist import load_runtime_config

        cfg = load_runtime_config() or {}
        mode = str((cfg.get("safety") or {}).get("mode") or "").strip().lower()
        if mode in SAFETY_MODES:
            return mode
    except Exception:  # noqa: BLE001
        pass
    return DEFAULT_SAFETY_MODE


def is_private_endpoint(base_url: str) -> bool:
    """判断 base_url 指向的是否为内网/本机地址。

    覆盖：127.0.0.0/8、10/8、172.16/12、192.168/16、::1、
          localhost、*.local / *.internal / *.lan
    解析不出来的一律按**公网**处理（fail-closed）。
    """
    url = (base_url or "").strip()
    if not url:
        # 没有地址就没有出校 —— 本地协议厂商允许留空
        return True
    if "://" not in url:
        url = "http://" + url
    try:
        host = (urlparse(url).hostname or "").strip().lower()
    except Exception:  # noqa: BLE001
        return False
    if not host:
        return False
    if host in _PRIVATE_HOSTS or host.endswith(_PRIVATE_HOST_SUFFIX):
        return True
    try:
        ip = ip_address(host)
    except ValueError:
        # 域名形式（非 IP）：无法判定，按公网处理
        return False
    return bool(
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_reserved
    )


@dataclass
class RouteDecision:
    level: str                 # 数据定级 L1~L5
    egress: bool               # 是否离开校内网络
    route: str                 # "local" | "cloud"
    action: str                # "pass" | "warn" | "block" | "redact"
    allowed: bool              # 是否允许发出
    reason: str = ""
    findings: List[dict] = None  # type: ignore[assignment]
    redacted: bool = False

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "egress": self.egress,
            "route": self.route,
            "action": self.action,
            "allowed": self.allowed,
            "reason": self.reason,
            "findings": self.findings or [],
            "redacted": self.redacted,
        }


def decide(
    base_url: str,
    classification: Classification,
    *,
    protocol: str = "openai",
    mode: Optional[str] = None,
) -> RouteDecision:
    """给出本次调用的路由决策。

    protocol == "local" 且地址为空时视为校内（Ollama/vLLM 常见配置）。
    """
    mode = (mode or get_safety_mode()).strip().lower()
    if mode not in SAFETY_MODES:
        mode = DEFAULT_SAFETY_MODE

    # 本地协议厂商 + 未填地址 = 本机推理服务
    private = is_private_endpoint(base_url) or (
        protocol == "local" and not (base_url or "").strip()
    )
    route = "local" if private else "cloud"
    egress = not private
    findings = [f.to_dict() for f in classification.findings]

    if not egress:
        return RouteDecision(
            level=classification.level, egress=False, route="local",
            action="pass", allowed=True,
            reason="目标为校内/本机推理服务，数据未出校",
            findings=findings,
        )

    if mode == "off":
        return RouteDecision(
            level=classification.level, egress=True, route="cloud",
            action="pass", allowed=True,
            reason="安全策略已关闭（EDUFORGE_SAFETY_MODE=off），本次发往云端",
            findings=findings,
        )

    if classification.level and level_rank(classification.level) < level_rank(BLOCK_LEVEL):
        return RouteDecision(
            level=classification.level, egress=True, route="cloud",
            action="pass", allowed=True,
            reason=f"数据定级 {classification.level}（未达 {BLOCK_LEVEL}），允许发往云端",
            findings=findings,
        )

    # 出校 + 达到敏感级别
    kinds = "、".join(f["label"] for f in findings) or "敏感信息"
    hit_kinds = {f["kind"] for f in findings}

    if mode == "warn":
        return RouteDecision(
            level=classification.level, egress=True, route="cloud",
            action="warn", allowed=True,
            reason=(f"检测到 {kinds}（定级 {classification.level}），"
                    f"本次将原样发往云端厂商。设为 enforce 可阻断，"
                    f"设为 sanitize 可在本地脱敏后发送"),
            findings=findings,
        )

    if mode == "sanitize":
        if hit_kinds & NON_REDACTABLE_KINDS:
            # 试题类内容脱敏无效，只能靠本地模型 —— 见 NON_REDACTABLE_KINDS 注释
            return RouteDecision(
                level=classification.level, egress=True, route="cloud",
                action="block", allowed=False,
                reason=(f"检测到 {kinds}（定级 {classification.level}）。"
                        f"其中考试题面无法脱敏后上云（抹掉题面就失去了全部用途），"
                        f"请改用校内/内网模型处理"),
                findings=findings,
            )
        return RouteDecision(
            level=classification.level, egress=True, route="cloud",
            action="redact", allowed=True, redacted=True,
            reason=(f"检测到 {kinds}（定级 {classification.level}），"
                    f"已在本地脱敏（抹去姓名/手机号/学号等身份标识，保留教学语义）后发往云端"),
            findings=findings,
        )

    # enforce
    return RouteDecision(
        level=classification.level, egress=True, route="cloud",
        action="block", allowed=False,
        reason=(f"检测到 {kinds}（定级 {classification.level}），"
                f"按当前策略禁止发往云端。请改用校内/内网模型，"
                f"或先移除敏感信息后重试"),
        findings=findings,
    )
