"""厂商（Provider）适配注册表 —— 全项目厂商配置的唯一真源。

背景
----
此前 base_url / 默认模型 / 鉴权方式被硬编码在 4 处且互相矛盾：
`llm_client.py`(2处)、`persist.py`、`api_routes.py`、`services/llm/service.py`。
任何一处更新不同步，就会出现"配置成功但调用失败"。

设计原则
--------
1. **唯一真源**：所有厂商信息只在此文件定义，其余模块一律引用。
2. **不臆断模型名**：`default_model` 仅作"拉取失败时的最后兜底"；
   正确路径是调用 `GET /api/llm/models/live` 用用户自己的 Key 拉取厂商**实时**列表。
   （历史教训：本项目曾误判真实存在的 `deepseek-v4-pro` 为"不存在"；
   也曾把已退役的 `deepseek-chat` 当作推荐值 —— 两者都是硬编码猜测的代价。）
3. **能力声明**：显式声明是否支持 视觉/工具调用/JSON模式/流式/Embedding，
   让上层在调用前就能判断"这个模型能不能干这件事"，而不是调用后报错。

端点取值依据（2026-09 核实）
----------------------------
- 阿里云百炼：https://dashscope.aliyuncs.com/compatible-mode/v1
  （Key 与地域绑定；已实测可拉取 249 个模型）
- DeepSeek：https://api.deepseek.com
  （官方文档 base_url 不带 /v1；deepseek-chat / deepseek-reasoner 已于 2026-07-24 退役）
- 智谱：https://open.bigmodel.cn/api/paas/v4
- Moonshot：https://api.moonshot.cn/v1
- Gemini：https://generativelanguage.googleapis.com/v1beta/openai/
  （必须以 /openai/ 结尾，否则 404）
- Anthropic：https://api.anthropic.com/v1（原生协议，非 OpenAI 格式）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ProviderSpec:
    """一个厂商的接入规格。"""

    key: str                      # 内部标识，如 "dashscope"
    label: str                    # 展示名，如 "阿里云百炼"
    base_url: str                 # OpenAI 兼容根地址（local/demo 可为空）
    protocol: str = "openai"      # openai | anthropic | local | demo
    default_model: str = ""       # 仅兜底，优先用实时列表
    models_path: str = "/models"  # 拉取实时模型列表的路径
    auth_header: str = "Authorization"
    auth_prefix: str = "Bearer"   # 拼成 "Bearer <key>"
    extra_headers: Dict[str, str] = field(default_factory=dict)
    # 能力声明
    supports_vision: bool = False
    supports_tools: bool = False
    supports_json_mode: bool = False
    supports_stream: bool = True
    supports_embedding: bool = False
    # 是否允许用户自定义 base_url（本地/自建网关需要）
    allows_custom_base_url: bool = False
    docs_url: str = ""
    notes: str = ""


# ---------------------------------------------------------------------------
# 注册表
# ---------------------------------------------------------------------------

_PROVIDERS: Dict[str, ProviderSpec] = {
    "dashscope": ProviderSpec(
        key="dashscope",
        label="阿里云百炼（通义千问）",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        protocol="openai",
        default_model="qwen-plus",
        supports_vision=True,
        supports_tools=True,
        supports_json_mode=True,
        supports_embedding=True,
        allows_custom_base_url=True,   # 多地域：北京/新加坡/香港/美西
        docs_url="https://help.aliyun.com/zh/dashscope/developer-reference/openai-batch-interface",
        notes="API Key 与地域绑定，换地域需重新生成 Key；支持 DeepSeek-V4 / GLM / Kimi 等第三方模型托管。",
    ),
    "openai": ProviderSpec(
        key="openai",
        label="OpenAI",
        base_url="https://api.openai.com/v1",
        protocol="openai",
        default_model="gpt-4o-mini",
        supports_vision=True,
        supports_tools=True,
        supports_json_mode=True,
        supports_embedding=True,
        allows_custom_base_url=True,   # 兼容中转/代理
        docs_url="https://platform.openai.com/docs/api-reference",
    ),
    "deepseek": ProviderSpec(
        key="deepseek",
        label="DeepSeek",
        base_url="https://api.deepseek.com",
        protocol="openai",
        # 注意：deepseek-chat / deepseek-reasoner 已于 2026-07-24 退役，不可再用
        default_model="deepseek-v4-flash",
        supports_tools=True,
        supports_json_mode=True,
        supports_embedding=False,
        allows_custom_base_url=True,
        docs_url="https://api-docs.deepseek.com/",
        notes="官方 base_url 不带 /v1（客户端会自动兼容）；deepseek-chat/deepseek-reasoner 已退役。",
    ),
    "zhipu": ProviderSpec(
        key="zhipu",
        label="智谱 GLM",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        protocol="openai",
        default_model="glm-4-flash",
        supports_vision=True,
        supports_tools=True,
        supports_json_mode=True,
        supports_embedding=True,
        allows_custom_base_url=True,
        docs_url="https://open.bigmodel.cn/",
        notes="GLM-4.7-Flash 系列免费；新版 SDK 为 zai-sdk。",
    ),
    "moonshot": ProviderSpec(
        key="moonshot",
        label="Moonshot（Kimi）",
        base_url="https://api.moonshot.cn/v1",
        protocol="openai",
        default_model="moonshot-v1-8k",
        supports_tools=True,
        supports_json_mode=True,
        allows_custom_base_url=True,
        docs_url="https://platform.moonshot.cn/",
        notes="Kimi K2 系列支持超长上下文。",
    ),
    "gemini": ProviderSpec(
        key="gemini",
        label="Google Gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        protocol="openai",
        default_model="gemini-3-flash",
        supports_vision=True,
        supports_tools=True,
        supports_json_mode=True,
        allows_custom_base_url=True,
        docs_url="https://ai.google.dev/gemini-api/docs/openai",
        notes="兼容层地址必须以 /openai/ 结尾，否则 404；只接受 Google AI Studio Key。",
    ),
    "anthropic": ProviderSpec(
        key="anthropic",
        label="Anthropic Claude",
        base_url="https://api.anthropic.com/v1",
        protocol="anthropic",
        default_model="claude-sonnet-4-5",
        supports_vision=True,
        supports_tools=True,
        supports_json_mode=False,
        allows_custom_base_url=True,
        auth_header="x-api-key",
        auth_prefix="",
        extra_headers={"anthropic-version": "2023-06-01"},
        docs_url="https://platform.claude.com/docs/en/api/messages-examples",
        notes="原生 /messages 协议，非 OpenAI 格式；Opus 4.7+ 不再支持 temperature/top_p。",
    ),
    "local": ProviderSpec(
        key="local",
        label="本地 / 自建（Ollama·vLLM·LMDeploy）",
        base_url="",                 # 由用户填写，例如内网 http://192.168.1.100:8000/v1
        protocol="local",
        default_model="auto",
        supports_vision=True,        # 取决于实际部署的模型（如 qwen3-vl-8b）
        supports_tools=False,
        supports_stream=True,
        allows_custom_base_url=True,
        notes="适配 Ollama / vLLM / LMDeploy / Xinference 等 OpenAI 兼容服务；无需 Key 时留空即可。",
    ),
    "demo": ProviderSpec(
        key="demo",
        label="演示模式（不调用真实模型）",
        base_url="",
        protocol="demo",
        default_model="demo",
        supports_stream=True,
        notes=(
            "仅用于无密钥时体验界面流程。返回内容由模板拼装，"
            "**不具备真实推理能力**，所有输出必须显式标记 degraded，绝不可伪装成模型生成结果。"
        ),
    ),
}

# 前端/文档展示顺序
PROVIDER_ORDER: List[str] = [
    "dashscope", "deepseek", "zhipu", "moonshot",
    "openai", "gemini", "anthropic", "local", "demo",
]


def get_provider(provider: Optional[str]) -> ProviderSpec:
    """取厂商规格；未知厂商一律回落到 demo，绝不抛异常打断调用链。"""
    if not provider:
        return _PROVIDERS["demo"]
    return _PROVIDERS.get(str(provider).strip().lower(), _PROVIDERS["demo"])


def known_providers() -> List[str]:
    return list(PROVIDER_ORDER)


def resolve_base_url(provider: Optional[str], user_base_url: Optional[str] = None) -> str:
    """解析最终 base_url：用户自定义优先（若该厂商允许），否则用官方默认。

    统一在此处理尾斜杠，避免各处拼出 `//chat/completions` 这类错误地址。
    """
    spec = get_provider(provider)
    url = (user_base_url or "").strip()
    if spec.allows_custom_base_url and url:
        return url.rstrip("/")
    return spec.base_url.rstrip("/")


def resolve_model(provider: Optional[str], user_model: Optional[str] = None) -> str:
    """解析模型名：用户选择优先，否则用兜底默认值。"""
    spec = get_provider(provider)
    model = (user_model or "").strip()
    return model or spec.default_model


def build_auth_headers(provider: Optional[str], api_key: Optional[str]) -> Dict[str, str]:
    """按厂商协议构造鉴权头。密钥在此处统一 strip，避免尾部空格导致 401。"""
    spec = get_provider(provider)
    headers: Dict[str, str] = dict(spec.extra_headers)
    key = (api_key or "").strip()
    if not key:
        return headers
    if spec.protocol == "demo":
        return headers
    if spec.protocol == "local" and not key:
        return headers
    value = f"{spec.auth_prefix} {key}".strip() if spec.auth_prefix else key
    headers[spec.auth_header] = value
    return headers


def models_endpoint(provider: Optional[str], base_url: Optional[str] = None) -> str:
    """实时模型列表地址（各厂商 OpenAI 兼容模式下基本一致）。"""
    root = resolve_base_url(provider, base_url)
    spec = get_provider(provider)
    if spec.protocol in ("demo",):
        return ""
    return f"{root}{spec.models_path}"


def supports(provider: Optional[str], capability: str) -> bool:
    """查询厂商是否具备某项能力，如 supports("dashscope", "vision")。"""
    spec = get_provider(provider)
    return bool(getattr(spec, f"supports_{capability}", False))


def provider_payload() -> List[Dict[str, object]]:
    """给前端设置页的厂商元数据（不含任何密钥）。"""
    out: List[Dict[str, object]] = []
    for key in PROVIDER_ORDER:
        spec = _PROVIDERS[key]
        out.append({
            "key": spec.key,
            "label": spec.label,
            "base_url": spec.base_url,
            "default_model": spec.default_model,
            "protocol": spec.protocol,
            "allows_custom_base_url": spec.allows_custom_base_url,
            "capabilities": {
                "vision": spec.supports_vision,
                "tools": spec.supports_tools,
                "json_mode": spec.supports_json_mode,
                "stream": spec.supports_stream,
                "embedding": spec.supports_embedding,
            },
            "docs_url": spec.docs_url,
            "notes": spec.notes,
        })
    return out
