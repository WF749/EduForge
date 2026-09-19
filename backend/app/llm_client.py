"""LLM calls: OpenAI-compatible clients + demo fallback."""
import os
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List

import httpx
from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAI

_PROJECT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT / ".env")

# Avoid SDK default httpx client (older openai + httpx 0.28+ used removed `proxies=` kwarg)
# 增加超时以适应教案和PPT的长时间生成需求
_HTTP_TIMEOUT = httpx.Timeout(180.0, connect=30.0)


# 对话历史的轮数上限。
# 抽成常量是为了让"界面能如实说出带上几轮" —— 写死在切片里的话，
# 展示文案与实际行为迟早对不上，而这种不一致教师是发现不了的。
HISTORY_TURNS = 20


def _history_from_payload(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    history = body.get("history")
    if not isinstance(history, list):
        return []
    messages: List[Dict[str, Any]] = []
    for item in history[-HISTORY_TURNS:]:
        if not isinstance(item, dict) or item.get("role") not in ("user", "assistant"):
            continue
        content = item.get("content")
        if isinstance(content, str) and content.strip():
            messages.append({"role": item["role"], "content": content.strip()[:12_000]})
    return messages


def _system_prefix(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    """可选的 system 消息。

    单独抽出来是为了让文字链路和多模态链路取到**同一份** system ——
    只在其中一条上支持，将来带图提问时会静默丢掉语境（这类"少了一段"
    的 bug 不报错、不入日志，只能靠不重复写两份来避免）。
    """
    system = (body.get("system") or "").strip()
    return [{"role": "system", "content": system}] if system else []


def _messages_from_payload(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    messages: List[Dict[str, Any]] = []
    # 可选 system：工作台对话要带上"这节课的语境 + 智能体身份"。
    # 语境是长期背景，不能拼进用户消息（模型会以为教师刚说了那一长串）。
    # 不传 system 的既有调用方行为完全不变。
    messages.extend(_system_prefix(body))
    messages.extend(_history_from_payload(body))
    msg = (body.get("message") or "").strip()
    messages.append({"role": "user", "content": msg})
    return messages


# ---------------------------------------------------------------------------
# 数据流向守卫
# ---------------------------------------------------------------------------
# 教案 / PPT / 动画 / 游戏 / 对话的生成走本模块，而不是 core/llm_gateway，
# 所以合规判定**必须也在这里做一次** —— 只装在网关上等于主链路完全裸奔。
# 守卫实现统一放在 app/safety/guard.py，与 services/llm/service.py 共用。
# ---------------------------------------------------------------------------


def _guard(messages: List[Dict[str, Any]], base_url: str, provider: str) -> Dict[str, Any]:
    from .safety.guard import guard_flow

    return guard_flow(messages=messages, base_url=base_url, provider=provider)


def _block_notice(flow: Dict[str, Any]) -> str:
    from .safety.guard import block_notice

    return block_notice(flow)


def _apply_redaction(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    from .safety.guard import apply_redaction

    return apply_redaction(messages)


def _dashscope_base() -> str:
    return "https://dashscope.aliyuncs.com/compatible-mode/v1"


def _friendly_http_error(status: int) -> str:
    """把 HTTP 状态码翻译成用户能看懂的原因提示。"""
    return {
        400: "请求参数错误（最常见原因：模型名不正确，请到设置页重新选择模型）",
        401: "API Key 无效、已过期或额度已用尽，请到设置页重新配置密钥",
        403: "没有该模型/接口的访问权限，请检查账户权限或套餐",
        404: "接口地址或模型不存在，请检查 base_url 与模型名",
        408: "请求超时，请稍后重试",
        422: "请求参数不合法（可能是模型不支持该参数）",
        429: "触发限流或余额不足，请稍后重试或充值",
        500: "服务商内部错误，请稍后重试",
        502: "网关错误，请稍后重试",
        503: "服务暂不可用，请稍后重试",
    }.get(status, f"调用失败（HTTP {status}）")


def _image_url_from_base64(raw: str) -> str:
    raw = (raw or "").strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    if raw.startswith("data:image"):
        return raw
    return f"data:image/jpeg;base64,{raw}"


def _vision_model(provider: str, user_model: str) -> str:
    if provider == "dashscope":
        return "qwen-vl-plus"
    if provider == "openai":
        m = (user_model or "").lower()
        if "gpt-4" in m or "gpt-4o" in m:
            return user_model or "gpt-4o"
        return "gpt-4o"
    if provider == "zhipu":
        return "glm-4v"
    if provider == "moonshot":
        return user_model or "moonshot-v1-8k"
    return user_model or "qwen-vl-plus"


def _messages_multimodal(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    user_text = (body.get("message") or "").strip() or "请描述图片中的教学内容，并给出教学建议。"
    img_url = _image_url_from_base64(body.get("image_base64") or "")
    content: List[Dict[str, Any]] = [
        {"type": "image_url", "image_url": {"url": img_url}},
        {"type": "text", "text": user_text},
    ]
    return [*_system_prefix(body), *_history_from_payload(body), {"role": "user", "content": content}]


async def stream_chat_completion(body: Dict[str, Any]) -> AsyncIterator[str]:
    """Yield text deltas for chat stream (text or multimodal when image_base64 set)."""
    from . import persist

    # 优先使用前端传入的配置（模型、provider），确保测试和实际对话使用同一个模型
    settings = persist.get_active_llm_settings()
    provider = body.get("provider") or settings["provider"]
    
    # 如果前端传入了有效的模型（非空字符串），覆盖后端配置的模型
    # 注意：空字符串不覆盖，使用后端配置中的模型或默认模型
    model_from_frontend = body.get("model")
    if model_from_frontend and isinstance(model_from_frontend, str) and model_from_frontend.strip():
        settings["model"] = model_from_frontend.strip()

    if body.get("image_base64"):
        messages = _messages_multimodal(body)
        if provider == "demo":
            ut = (body.get("message") or "").strip()[:2000]
            text = (
                "[演示模式] 已收到图片。请在「设置」中选择通义千问等支持视觉的供应商并配置 API Key。\n\n"
                f"【用户问题】{ut}"
            )
            for i in range(0, len(text), 8):
                yield text[i : i + 8]
            return
        if provider in ("deepseek", "local", "anthropic", "gemini"):
            yield (
                f"当前服务商 `{provider}` 在本项目中未配置多模态识图，请切换到 "
                "`dashscope`（通义千问 qwen-vl）或 `openai`（gpt-4o）后重试。"
            )
            return
    else:
        messages = _messages_from_payload(body)
        if provider == "demo":
            text = (
                "[演示模式] 请在「设置」中配置 API Key 并选择服务商。\n\n"
                "当前为离线演示回复：\n"
                + ((messages[0].get("content") or "")[:2000] if messages else "")
            )
            for i in range(0, len(text), 8):
                yield text[i : i + 8]
            return

    api_key = (settings["api_key"] or os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()
    model = settings["model"] or "qwen-plus"
    if body.get("image_base64"):
        model = _vision_model(provider, model)
    base_url = settings["base_url"]

    if provider == "dashscope":
        base_url = _dashscope_base()
    if not base_url and provider in ("openai", "deepseek", "zhipu", "moonshot"):
        base_url = {
            "openai": "https://api.openai.com/v1",
            "deepseek": "https://api.deepseek.com/v1",
            "zhipu": "https://open.bigmodel.cn/api/paas/v4",
            "moonshot": "https://api.moonshot.cn/v1",
        }.get(provider)

    # 数据流向守卫：必须在发出请求之前。命中阻断时只产出提示，
    # 绝不发送 —— 抛异常会截断 SSE 流，前端只会看到连接中断。
    flow = _guard(messages, base_url, provider)
    if not flow.get("allowed", True):
        yield _block_notice(flow)
        return
    if flow.get("action") == "redact":
        messages = _apply_redaction(messages)

    if not api_key:
        yield "未配置 API Key：请在设置页保存密钥，或在项目根目录 .env 中设置 DASHSCOPE_API_KEY。"
        return

    # 禁用SSL验证，解决某些网络环境下的证书问题
    http_client = httpx.AsyncClient(timeout=_HTTP_TIMEOUT, verify=False)
    try:
        # 直接使用 httpx 发送请求，避免 OpenAI SDK 的问题
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": model,
            "messages": messages,
            "temperature": settings["temperature"],
            "stream": True
        }
        
        async with http_client.stream("POST", url, headers=headers, json=data) as response:
            # 关键修复：httpx.stream() 对 4xx/5xx 不会抛异常，必须显式检查状态码。
            # 否则错误响应体里没有 "data: " 行，会静默输出空内容，前端毫无提示。
            if response.status_code != 200:
                raw = (await response.aread()).decode("utf-8", "replace")[:500]
                yield (
                    f"\n\n[LLM 调用失败] HTTP {response.status_code} · "
                    f"{_friendly_http_error(response.status_code)}\n"
                    f"- provider: {provider}\n"
                    f"- model: {model}\n"
                    f"- base_url: {base_url}\n"
                    f"- 服务端返回：{raw}"
                )
                return
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    import json
                    try:
                        chunk = json.loads(line[6:])
                        if chunk.get("choices") and chunk["choices"][0].get("delta", {}).get("content"):
                            yield chunk["choices"][0]["delta"]["content"]
                        if chunk.get("choices") and chunk["choices"][0].get("finish_reason"):
                            break
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        # 提供更详细的错误信息，帮助调试
        error_info = f"[LLM 错误] {type(e).__name__}: {e!s}"
        if provider and model:
            error_info = f"[LLM 错误] provider={provider}, model={model}: {type(e).__name__}: {e!s}"
        # 注意：调试信息严禁包含任何密钥片段
        safe_debug = (
            f"\n\n[调试信息]\n"
            f"- provider: {provider}\n"
            f"- model: {model}\n"
            f"- base_url: {base_url}\n"
            f"- 请检查 API Key 是否已正确配置（出于安全考虑不输出密钥信息）"
        )
        yield f"\n\n{error_info}{safe_debug}"
    finally:
        await http_client.aclose()


def blocking_chat(messages: List[Dict[str, Any]], max_tokens: int = 2048) -> str:
    """Single non-streaming completion for summaries / outlines / JSON extraction."""
    from . import persist

    settings = persist.get_active_llm_settings()
    provider = settings["provider"]
    if provider == "demo":
        return "演示模式：请配置真实 API Key 后重试。"

    api_key = (settings["api_key"] or os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()
    model = settings["model"] or "qwen-plus"
    base_url = settings["base_url"]
    if provider == "dashscope":
        base_url = _dashscope_base()
    if not base_url and provider in ("openai", "deepseek", "zhipu", "moonshot"):
        base_url = {
            "openai": "https://api.openai.com/v1",
            "deepseek": "https://api.deepseek.com/v1",
            "zhipu": "https://open.bigmodel.cn/api/paas/v4",
            "moonshot": "https://api.moonshot.cn/v1",
        }.get(provider)
    # 数据流向守卫：必须在发出请求之前。
    # 这里可以抛异常 —— 调用方都在 FastAPI 路由里，全局异常处理器会把它
    # 转成 403 + 可操作提示，用户看到的是"为什么被拦下"而不是空结果。
    flow = _guard(messages, base_url, provider)
    if not flow.get("allowed", True):
        from .core.errors import DataEgressBlockedError

        raise DataEgressBlockedError(flow.get("reason") or "敏感数据外发被阻断")
    if flow.get("action") == "redact":
        messages = _apply_redaction(messages)

    if not api_key:
        return ""

    # 禁用SSL验证，解决某些网络环境下的证书问题
    http_client = httpx.Client(timeout=_HTTP_TIMEOUT, verify=False)
    try:
        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=http_client,
        )
        r = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=settings["temperature"],
        )
        return (r.choices[0].message.content or "").strip()
    finally:
        http_client.close()
