"""统一 LLM 网关 —— 全项目调用大模型的唯一入口。

为什么必须有这一层
------------------
改造前，`llm_client.py` / `services/llm/*.py` / `api_routes.py` 各自发起 HTTP 请求，
带来三个真实故障：
  1. **HTTP 错误被静默吞掉**：`httpx.stream()` 对 4xx/5xx **不抛异常**，
     老代码只解析 `data: ` 开头的行，错误响应 0 行匹配 → 输出空白。
     用户看到"对话没反应"，实际是 401 密钥无效。
  2. **厂商信息四处硬编码且互相矛盾**：同一厂商的 base_url 在 4 处各写一份。
  3. **没有任何度量**：不知道耗时、token、成功率、成本。

本网关统一负责：鉴权构造、状态码校验、错误映射、重试、指标采集、降级标记，
以及**数据流向判定**（敏感输入是否会被发往校外，见 app/safety/）。
"""

from __future__ import annotations

import contextvars
import json
import time
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from .errors import (
    AuthError,
    DataEgressBlockedError,
    LLMTimeoutError,
    LLMUnavailableError,
    ModelNotFoundError,
    QuotaError,
    UnsupportedCapabilityError,
)
from .logging_setup import get_logger, set_context
from .observability import Span, estimate_cost_cny, metrics
from .providers import build_auth_headers, get_provider, resolve_base_url, resolve_model
from .sampling import describe as describe_sampling, resolve_temperature

log = get_logger("llm.gateway")

DEFAULT_TIMEOUT = 120.0
MAX_RETRIES = 2          # 首次 + 2 次重试
RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}

# 本次请求最近一次的数据流向决策。
# 用 contextvar 而不是全局变量：后端是并发服务，全局变量会串到别人的请求上。
_data_flow_var: contextvars.ContextVar[Optional[Dict[str, Any]]] = (
    contextvars.ContextVar("eduforge_data_flow", default=None)
)


def new_data_flow_slot() -> Dict[str, Any]:
    """在请求开始时建一个共享槽位，供端点写入、中间件读回。

    Starlette 的中间件与端点运行在**不同的 task** 上：子 task 对 ContextVar
    执行 `.set()` 不会回传给父 task，但对同一个 dict 对象的**原地修改**是
    两边共享的。所以这里塞一个空 dict 进去，端点往里写，中间件结束后读它。
    """
    slot: Dict[str, Any] = {}
    _data_flow_var.set(slot)
    return slot


def set_data_flow(decision: Optional[Dict[str, Any]]) -> None:
    """记录本次调用的数据流向决策。

    优先原地写入中间件建的槽位（这样才能回传给中间件加上响应头）；
    没有槽位时（脚本、后台任务直接调用）退化为普通 set。
    """
    cur = _data_flow_var.get()
    if isinstance(cur, dict):
        cur.clear()
        if decision:
            cur.update(decision)
    else:
        _data_flow_var.set(decision)


def get_data_flow() -> Optional[Dict[str, Any]]:
    cur = _data_flow_var.get()
    return dict(cur) if cur else None


# ---------------------------------------------------------------------------
# 错误映射
# ---------------------------------------------------------------------------

def _map_http_error(status: int, body: str, provider: str, model: str) -> Exception:
    """把 HTTP 状态码翻译成可操作的业务异常。

    message 里给出"用户该做什么"，而不是只抛技术细节。
    """
    snippet = (body or "")[:300].replace("\n", " ")
    base = f"[{provider}/{model}] "

    if status in (401, 403):
        return AuthError(
            base + f"API Key 无效、已过期或无权访问（HTTP {status}）",
            detail=snippet,
        )
    if status == 429:
        return QuotaError(
            base + f"请求过于频繁或额度已用尽（HTTP {status}）",
            detail=snippet,
        )
    if status == 404:
        return ModelNotFoundError(
            base + f"模型不存在或接口地址有误（HTTP {status}）",
            detail=snippet,
        )

    # 账户欠费：百炼用 HTTP 400 + code=Arrearage 表示，各家措辞不同但都带这几个词。
    # 若不单独识别，用户只会看到"调用失败（HTTP 400）"，完全不知道该去充值。
    lowered = snippet.lower()
    if any(k in lowered for k in ("arrearage", "overdue", "欠费", "余额不足",
                                  "insufficient_balance", "account is in good standing")):
        return QuotaError(
            base + "账户已欠费或余额不足，请到厂商控制台充值后重试",
            detail=snippet,
        )

    if status >= 500:
        return LLMUnavailableError(
            base + f"厂商服务暂时不可用（HTTP {status}）",
            detail=snippet,
        )
    return LLMUnavailableError(base + f"调用失败（HTTP {status}）", detail=snippet)


def _extract_error_body(text: str) -> str:
    """从错误响应里提取最有价值的一句，优先厂商返回的 error.message。"""
    if not text:
        return ""
    try:
        d = json.loads(text)
        if isinstance(d, dict):
            err = d.get("error")
            if isinstance(err, dict):
                return str(err.get("message") or err.get("code") or "")
            if isinstance(err, str):
                return err
    except Exception:
        pass
    return text


# ---------------------------------------------------------------------------
# 数据流向判定
# ---------------------------------------------------------------------------

def _evaluate_data_flow(
    *,
    system: str,
    history: List[Dict[str, str]],
    prompt: str,
    base_url: str,
    protocol: str,
) -> Dict[str, Any]:
    """对本次调用做敏感数据定级 + 出校判定。

    返回统一 dict（而非 dataclass），因为它要同时进日志、追踪与 HTTP 响应头。

    判定本身失败时**按最坏情况处理**（视为不允许外发）——
    宁可误拦，也不能因为检测出错就悄悄放行。
    """
    try:
        from ..safety import classify, decide

        clf = classify(
            system or "",
            "\n".join(str(h.get("content") or "") for h in history),
            prompt or "",
        )
        d = decide(base_url, clf, protocol=protocol)
        return d.to_dict()
    except Exception as e:  # noqa: BLE001
        log.error("数据流向判定失败，按最坏情况处理: %s", e)
        return {
            "level": "L3", "egress": True, "route": "cloud",
            "action": "block", "allowed": False, "findings": [],
            "reason": f"数据流向判定失败（{type(e).__name__}），已按最坏情况阻断本次外发",
        }


# ---------------------------------------------------------------------------
# 核心：非流式调用
# ---------------------------------------------------------------------------

def llm_chat(
    prompt: str,
    *,
    purpose: str = "chat",
    history: Optional[List[Dict[str, str]]] = None,
    system: str = "",
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_retries: int = MAX_RETRIES,
    json_mode: bool = False,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    stage: str = "",
) -> str:
    """调用大模型，返回完整文本。失败抛 AppError（绝不返回空串冒充成功）。

    `api_key` / `base_url` 用于「保存前试连」：设置页需要拿输入框里尚未落盘的
    Key 探测厂商，此时不能要求用户先保存再测试。

    `purpose` / `stage` 决定本次调用的**任务用途与执行阶段**，供采样策略解析温度。
    `temperature` 只在调用点**明确指定**时才传（内部约定，如规划/修复/验证），
    普通调用一律留空走自动策略。
    """
    from ..persist import get_active_llm_settings

    cfg = get_active_llm_settings()
    prov_key = provider or cfg.get("provider") or "demo"
    spec = get_provider(prov_key)
    if api_key is None:
        api_key = cfg.get("api_key") or ""
    api_key = api_key.strip()
    custom_base = (base_url or "").strip() or None
    base_url = resolve_base_url(prov_key, custom_base)
    model_name = resolve_model(prov_key, model or cfg.get("model"))

    # 采样参数**按本次请求**解析，不改写全局配置 —— 并发任务会互相污染。
    sampling = resolve_temperature(
        purpose=purpose, stage=stage, explicit=temperature,
        config=cfg, provider=prov_key, model=model_name,
    )
    log.debug(describe_sampling(sampling))

    set_context(agent_name=purpose, step_name=f"{prov_key}/{model_name}")

    if spec.protocol == "demo":
        # 演示模式：显式标记降级，让调用方与前端都能感知"这不是真实模型输出"
        metrics.record(Span(
            kind="llm", name="demo", provider=prov_key, model="demo",
            status="degraded", degraded=True, duration_ms=0,
            meta={"purpose": purpose, "reason": "未配置可用模型"},
        ).finish("degraded"))
        return _demo_answer(prompt)

    if not api_key and spec.protocol != "local":
        from .errors import ConfigError
        raise ConfigError(
            f"尚未配置 {spec.label} 的 API Key",
            code="E1002",
            status=400,
            hint="请到「设置」页填写 API Key 后重试。",
        )

    if json_mode and not spec.supports_json_mode:
        raise UnsupportedCapabilityError(f"{spec.label} 未声明支持 JSON 输出模式")

    # ---- 数据流向判定（合规自证的核心）--------------------------------
    # 必须放在消息组装**之前**：一旦被阻断，这些内容根本不该离开进程。
    # system / history / prompt 都要检查 —— 名单往往出现在历史消息里，
    # 只看 prompt 会漏。
    flow = _evaluate_data_flow(
        system=system, history=history or [], prompt=prompt,
        base_url=base_url, protocol=spec.protocol,
    )
    set_data_flow(flow)

    if not flow.get("allowed", True):
        # 记录到追踪，便于事后审计"谁在什么时候被拦下了"
        metrics.record(Span(
            kind="llm", name="data_egress_blocked", provider=prov_key,
            model=model_name, status="blocked", duration_ms=0,
            meta={"purpose": purpose, "level": flow.get("level"),
                  "findings": [f["kind"] for f in flow.get("findings", [])]},
        ).finish("blocked"))
        raise DataEgressBlockedError(flow.get("reason") or "敏感数据外发被阻断")
    if flow.get("action") == "warn":
        log.warning("数据流向告警 [%s] %s", purpose, flow.get("reason"))

    # 需要脱敏时，先处理各段文本，再统一组装消息（避免组装两次）
    sys_text = system or ""
    hist_pairs: List[tuple] = [
        (h.get("role"), str(h.get("content")))
        for h in (history or [])
        if h.get("role") and h.get("content")
    ]
    if flow.get("action") == "redact":
        from ..safety.redact import redact

        sys_text = redact(sys_text)[0]
        prompt = redact(prompt)[0]
        hist_pairs = [(r, redact(c)[0]) for r, c in hist_pairs]

    messages: List[Dict[str, str]] = []
    if sys_text:
        messages.append({"role": "system", "content": sys_text})
    for role, content in hist_pairs:
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": prompt})

    payload: Dict[str, Any] = {
        "model": model_name,
        "messages": messages,
        "stream": False,
    }
    if sampling.sent:
        payload["temperature"] = float(sampling.value)
    if max_tokens:
        payload["max_tokens"] = int(max_tokens)
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    url = f"{base_url}/chat/completions"
    headers = {"Content-Type": "application/json"}
    headers.update(build_auth_headers(prov_key, api_key))

    last_exc: Optional[Exception] = None
    for attempt in range(1, max_retries + 2):
        span = Span(kind="llm", name=model_name, provider=prov_key, model=model_name, attempt=attempt,
                    meta={"purpose": purpose, "stage": stage, "sampling": sampling.to_dict()})
        try:
            with httpx.Client(timeout=timeout, verify=False) as client:
                resp = client.post(url, headers=headers, json=payload)
                # 关键：显式校验状态码。httpx 不会对 4xx/5xx 抛异常，
                # 老代码正是漏了这一步，导致所有错误静默变成空输出。
                if resp.status_code >= 400:
                    raise _map_http_error(
                        resp.status_code, _extract_error_body(resp.text), prov_key, model_name
                    )
                data = resp.json()

            choices = data.get("choices") or []
            if not choices:
                raise LLMUnavailableError(f"[{prov_key}/{model_name}] 响应中不含 choices", detail=str(data)[:300])
            content = (choices[0].get("message") or {}).get("content") or ""

            usage = data.get("usage") or {}
            span.prompt_tokens = int(usage.get("prompt_tokens") or 0)
            span.completion_tokens = int(usage.get("completion_tokens") or 0)
            span.total_tokens = int(usage.get("total_tokens") or span.prompt_tokens + span.completion_tokens)
            span.cost_cny = estimate_cost_cny(prov_key, model_name, span.prompt_tokens, span.completion_tokens)
            span.finish("ok")
            metrics.record(span)

            if not content.strip():
                # 模型返回空也算异常，不能静默通过
                raise LLMUnavailableError(
                    f"[{prov_key}/{model_name}] 模型返回空内容", detail=str(data)[:300]
                )
            return content

        except (AuthError, ModelNotFoundError, QuotaError, UnsupportedCapabilityError) as e:
            # 用户可自行修复的错误，重试没有意义
            span.finish("error", error=e)
            metrics.record(span)
            raise
        except Exception as e:
            last_exc = e
            span.finish("error", error=e)
            metrics.record(span)
            if attempt <= max_retries and _is_retryable(e):
                wait = 2 ** (attempt - 1)
                log.warning("LLM 调用失败，%ss 后重试(%d/%d): %s", wait, attempt, max_retries, e)
                time.sleep(wait)
                continue
            break

    if isinstance(last_exc, (LLMUnavailableError,)):
        raise last_exc
    raise LLMUnavailableError(
        f"[{prov_key}/{model_name}] 调用失败：{last_exc}",
        detail=str(last_exc)[:300],
    )


def llm_chat_json(prompt: str, **kw) -> Any:
    """要求模型输出 JSON 并解析；解析失败如实报错，不伪造默认值。"""
    kw["json_mode"] = True
    text = llm_chat(prompt, **kw)
    text = text.strip()
    # 模型常把 JSON 包在 ```json 代码块里
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except Exception as e:
        raise LLMUnavailableError(f"模型未返回合法 JSON: {e}", detail=text[:500])


def _is_retryable(e: Exception) -> bool:
    """只有瞬时故障才重试；鉴权/模型/参数错误重试纯属浪费额度。"""
    # 用户可自行修复的错误：重试无意义
    if isinstance(e, (AuthError, ModelNotFoundError, UnsupportedCapabilityError)):
        return False
    # 网络抖动 / 超时 / 服务端 5xx：值得退避重试
    if isinstance(e, (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError)):
        return True
    if isinstance(e, (LLMUnavailableError, QuotaError)):
        return True
    return False


# ---------------------------------------------------------------------------
# 流式调用
# ---------------------------------------------------------------------------

async def llm_stream(
    prompt: str,
    *,
    purpose: str = "chat",
    history: Optional[List[Dict[str, str]]] = None,
    system: str = "",
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    timeout: float = DEFAULT_TIMEOUT,
    stage: str = "",
) -> AsyncIterator[str]:
    """流式输出。**首包即校验状态码**，错误会以可读文本产出而非静默空白。

    采样策略与 `llm_chat` 完全一致（同一个 resolve_temperature），
    避免"同步和流式拿到不同的温度"。
    """
    from ..persist import get_active_llm_settings

    cfg = get_active_llm_settings()
    prov_key = provider or cfg.get("provider") or "demo"
    spec = get_provider(prov_key)
    api_key = cfg.get("api_key") or ""
    base_url = resolve_base_url(prov_key, cfg.get("base_url"))
    model_name = resolve_model(prov_key, model or cfg.get("model"))

    # 采样参数**按本次请求**解析，不改写全局配置 —— 并发任务会互相污染。
    sampling = resolve_temperature(
        purpose=purpose, stage=stage, explicit=temperature,
        config=cfg, provider=prov_key, model=model_name,
    )
    log.debug(describe_sampling(sampling))

    set_context(agent_name=purpose, step_name=f"{prov_key}/{model_name}")

    if spec.protocol == "demo":
        for chunk in _demo_answer(prompt):
            yield chunk
        return
    if not api_key and spec.protocol != "local":
        from .errors import ConfigError
        raise ConfigError("尚未配置 API Key", code="E1002", status=400,
                          hint="请到「设置」页填写 API Key 后重试。")

    # ---- 数据流向判定（与 llm_chat 同一套逻辑，必须在组装消息前）--------
    # 流式是用户输入最不可控的入口（自由对话），漏掉它等于防护形同虚设。
    flow = _evaluate_data_flow(
        system=system, history=history or [], prompt=prompt,
        base_url=base_url, protocol=spec.protocol,
    )
    set_data_flow(flow)

    if not flow.get("allowed", True):
        metrics.record(Span(
            kind="llm", name="data_egress_blocked", provider=prov_key,
            model=model_name, status="blocked", duration_ms=0,
            meta={"purpose": purpose, "stream": True, "level": flow.get("level"),
                  "findings": [f["kind"] for f in flow.get("findings", [])]},
        ).finish("blocked"))
        raise DataEgressBlockedError(flow.get("reason") or "敏感数据外发被阻断")
    if flow.get("action") == "warn":
        log.warning("数据流向告警 [%s] %s", purpose, flow.get("reason"))

    sys_text = system or ""
    hist_pairs: List[tuple] = [
        (h.get("role"), str(h.get("content")))
        for h in (history or [])
        if h.get("role") and h.get("content")
    ]
    if flow.get("action") == "redact":
        from ..safety.redact import redact

        sys_text = redact(sys_text)[0]
        prompt = redact(prompt)[0]
        hist_pairs = [(r, redact(c)[0]) for r, c in hist_pairs]

    messages: List[Dict[str, str]] = []
    if sys_text:
        messages.append({"role": "system", "content": sys_text})
    for role, content in hist_pairs:
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": prompt})

    payload: Dict[str, Any] = {
        "model": model_name,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if sampling.sent:
        payload["temperature"] = float(sampling.value)

    url = f"{base_url}/chat/completions"
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
    headers.update(build_auth_headers(prov_key, api_key))

    span = Span(kind="llm", name=model_name, provider=prov_key, model=model_name,
                meta={"purpose": purpose, "stage": stage, "stream": True,
                      "sampling": sampling.to_dict()})
    try:
        async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                # 关键修复：httpx.stream 不会因 4xx/5xx 抛异常，必须显式判断
                if resp.status_code >= 400:
                    body = (await resp.aread()).decode("utf-8", "replace")
                    err = _map_http_error(resp.status_code, _extract_error_body(body), prov_key, model_name)
                    span.finish("error", error=err)
                    metrics.record(span)
                    raise err

                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    usage = chunk.get("usage")
                    if usage:
                        span.prompt_tokens = int(usage.get("prompt_tokens") or 0)
                        span.completion_tokens = int(usage.get("completion_tokens") or 0)
                        span.total_tokens = int(usage.get("total_tokens") or 0)
                        span.cost_cny = estimate_cost_cny(
                            prov_key, model_name, span.prompt_tokens, span.completion_tokens
                        )
                    choices = chunk.get("choices") or []
                    if choices:
                        delta = choices[0].get("delta") or {}
                        text = delta.get("content")
                        if text:
                            yield text
        span.finish("ok")
        metrics.record(span)
    except httpx.TimeoutException as e:
        span.finish("error", error=e)
        metrics.record(span)
        raise LLMTimeoutError(f"[{prov_key}/{model_name}] 生成超时（>{timeout:.0f}s）")


# ---------------------------------------------------------------------------
# 演示模式：明确标记，绝不伪装
# ---------------------------------------------------------------------------

def _demo_answer(prompt: str) -> str:
    """演示模式的返回。**必须**让用户一眼看出这不是真实模型输出。"""
    return (
        "【演示模式 · 未调用真实模型】\n\n"
        f"我收到了你的问题：「{prompt[:100]}」\n\n"
        "当前尚未配置可用的 API Key，因此无法给出真实回答。\n"
        "请到「设置」页选择厂商并填写 API Key，保存后即可正常使用。\n\n"
        "（此提示由系统生成，不是模型输出。）"
    )
