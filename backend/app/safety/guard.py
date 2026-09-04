"""调用守卫：在**发出请求之前**做数据定级与出校判定。

为什么单独成模块
----------------
本项目历史上长出了 4 条彼此独立的 LLM 调用路径：

  1. `core/llm_gateway.py`       —— Agent 层（planner / executor / verifier）
  2. `llm_client.py`             —— 对话、内容生成、PPT 大纲
  3. `services/llm/service.py`   —— PPT / 课件 / 动画 / 游戏生成（再分发到各 provider）
  4. `services/llm/<provider>.py`—— 各厂商直连

第 4 条由第 3 条收口，所以真正需要插桩的是 1、2、3。
只装在网关上等于主生成链路完全裸奔 —— 而那恰恰是最容易粘贴学生名单的地方
（"把这次月考错题做成讲评 PPT"）。

本模块提供三个函数，供这三条链路以各自合适的方式调用：
  - `guard_flow()`      判定并返回决策（同时写入 contextvar，供响应头回传）
  - `block_notice()`    给终端用户看的拦截文案（流式用，抛异常会截断 SSE）
  - `apply_redaction()` sanitize 模式的本地脱敏

判定失败时的取向
----------------
放行但显式告警，而不是阻断。主生成链路是产品的核心功能，
检测模块自身异常不应该让整个产品不可用；同时告警会进日志与追踪，
管理员能看见"这段时间没在检查"。
（网关侧 `llm_gateway._evaluate_data_flow` 仍保持 fail-closed ——
那里拦下的是可控的附加能力，误拦代价低。）
"""

from __future__ import annotations

from typing import Any, Dict, List


def text_of(content: Any) -> str:
    """取出消息文本。多模态消息里 content 是 list，只取其中的 text 片段。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for c in content:
            if isinstance(c, dict) and c.get("type") == "text":
                parts.append(str(c.get("text") or ""))
        return "\n".join(parts)
    return str(content or "")


def guard_flow(
    *,
    messages: List[Dict[str, Any]] | None = None,
    prompt: str = "",
    history: List[Dict[str, str]] | None = None,
    system: str = "",
    base_url: str = "",
    provider: str = "",
) -> Dict[str, Any]:
    """对本次调用做敏感数据定级 + 出校判定，返回决策 dict。

    只判定、记录、写入 contextvar；**是否阻断开调用方决定** ——
    流式要产出提示文本（抛异常会截断 SSE），非流式才能抛 403。
    """
    try:
        from ..core.llm_gateway import _evaluate_data_flow, set_data_flow
        from ..core.providers import get_provider

        try:
            protocol = get_provider(provider).protocol if provider else "openai"
        except Exception:  # noqa: BLE001
            protocol = "openai"

        if messages is not None:
            text = "\n".join(text_of(m.get("content")) for m in messages)
            flow = _evaluate_data_flow(
                system="", history=[], prompt=text,
                base_url=base_url, protocol=protocol,
            )
        else:
            flow = _evaluate_data_flow(
                system=system, history=history or [], prompt=prompt,
                base_url=base_url, protocol=protocol,
            )

        set_data_flow(flow)     # 让中间件把结果写进响应头
        return flow
    except Exception as e:  # noqa: BLE001
        from ..core.logging_setup import get_logger

        get_logger("safety.guard").error("数据流向判定失败，本次按最坏情况告警: %s", e)
        return {
            "level": "L3", "egress": True, "route": "cloud",
            "action": "warn", "allowed": True, "findings": [],
            "reason": f"数据流向判定失败（{type(e).__name__}），本次调用未被检查",
        }


def block_notice(flow: Dict[str, Any]) -> str:
    """给终端用户看的拦截提示（用于流式输出）。"""
    from ..core.errors import DataEgressBlockedError

    err = DataEgressBlockedError(flow.get("reason") or "敏感数据外发被阻断")
    return (
        f"\n\n[数据合规拦截] 本次内容未发送到任何云端模型。\n"
        f"- 数据定级：{flow.get('level')}\n"
        f"- 原因：{flow.get('reason')}\n"
        f"- 处理建议：{err.hint}\n"
    )


def apply_redaction(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """sanitize 模式：就地脱敏消息文本，保留教学语义。"""
    try:
        from .redact import redact
    except Exception:  # noqa: BLE001
        return messages

    out: List[Dict[str, Any]] = []
    for m in messages:
        content = m.get("content")
        if not isinstance(content, str):
            out.append(m)
            continue
        out.append({**m, "content": redact(content)[0]})
    return out
