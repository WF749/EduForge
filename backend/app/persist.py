import threading
from typing import Any, Dict, Optional

from .core.json_store import atomic_write_json, read_json, update_json
from .core.providers import get_provider, resolve_base_url
from .paths import CHAT_STORE, CONFIG_JSON, FILE_REGISTRY

_lock = threading.RLock()


def _read_json(path, default: Any) -> Any:
    """兼容旧签名的读取；损坏时不再静默返回默认值（详见 json_store）。"""
    return read_json(path, default)


def _write_json(path, data: Any) -> None:
    """兼容旧签名的写入；改为原子写，避免半截文件损坏配置。"""
    atomic_write_json(path, data)


def _encrypt_api_keys(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """加密配置中的API Key"""
    from .core.crypto import crypto_utils
    
    result = dict(cfg)
    api_keys = result.get("apiKeys")
    if api_keys and isinstance(api_keys, dict):
        encrypted_keys = {}
        for provider, key in api_keys.items():
            if key and isinstance(key, str) and not key.startswith("encrypted:"):
                encrypted_key = crypto_utils.encrypt(key)
                encrypted_keys[provider] = f"encrypted:{encrypted_key}" if encrypted_key else ""
            else:
                encrypted_keys[provider] = key
        result["apiKeys"] = encrypted_keys
    return result


def _decrypt_api_keys(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """解密配置中的API Key"""
    from .core.crypto import crypto_utils
    
    result = dict(cfg)
    api_keys = result.get("apiKeys")
    if api_keys and isinstance(api_keys, dict):
        decrypted_keys = {}
        for provider, key in api_keys.items():
            if key and isinstance(key, str) and key.startswith("encrypted:"):
                encrypted_key = key[len("encrypted:"):]
                decrypted_key = crypto_utils.decrypt(encrypted_key)
                decrypted_keys[provider] = decrypted_key or ""
            else:
                decrypted_keys[provider] = key
        result["apiKeys"] = decrypted_keys
    return result


def load_runtime_config() -> Dict[str, Any]:
    with _lock:
        cfg = _read_json(CONFIG_JSON, {})
        if not cfg:
            cfg = _load_default_config_from_env()
        else:
            cfg = _decrypt_api_keys(cfg)
        return cfg


def _load_default_config_from_env() -> Dict[str, Any]:
    import os
    cfg = {
        "provider": os.getenv("DEFAULT_LLM_PROVIDER", "demo"),
        "apiKeys": {},
        "models": {},
        "temperature": 0.7,
    }
    if os.getenv("DASHSCOPE_API_KEY"):
        cfg["apiKeys"]["dashscope"] = os.getenv("DASHSCOPE_API_KEY")
        # 此前误用 OPENAI_MODEL 作为百炼的模型名环境变量，属于复制粘贴错误
        cfg["models"]["dashscope"] = os.getenv("DASHSCOPE_MODEL", "qwen-plus")
    if os.getenv("OPENAI_API_KEY"):
        cfg["apiKeys"]["openai"] = os.getenv("OPENAI_API_KEY")
        cfg["models"]["openai"] = os.getenv("OPENAI_MODEL", "gpt-4o")
    if os.getenv("DEEPSEEK_API_KEY"):
        cfg["apiKeys"]["deepseek"] = os.getenv("DEEPSEEK_API_KEY")
        # 注意：deepseek-chat / deepseek-reasoner 已于 2026-07-24 退役，不可再作为默认值
        cfg["models"]["deepseek"] = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    if os.getenv("ZHIPU_API_KEY"):
        cfg["apiKeys"]["zhipu"] = os.getenv("ZHIPU_API_KEY")
        cfg["models"]["zhipu"] = os.getenv("ZHIPU_MODEL", "glm-4-flash")
    if os.getenv("MOONSHOT_API_KEY"):
        cfg["apiKeys"]["moonshot"] = os.getenv("MOONSHOT_API_KEY")
        cfg["models"]["moonshot"] = os.getenv("MOONSHOT_MODEL", "moonshot-v1-8k")
    if os.getenv("GEMINI_API_KEY"):
        cfg["apiKeys"]["gemini"] = os.getenv("GEMINI_API_KEY")
        cfg["models"]["gemini"] = os.getenv("GEMINI_MODEL", "gemini-3-flash")
    if os.getenv("ANTHROPIC_API_KEY"):
        cfg["apiKeys"]["anthropic"] = os.getenv("ANTHROPIC_API_KEY")
        cfg["models"]["anthropic"] = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
    return cfg


def save_runtime_config(cfg: Dict[str, Any]) -> None:
    with _lock:
        encrypted_cfg = _encrypt_api_keys(cfg)
        _write_json(CONFIG_JSON, encrypted_cfg)


def load_chat_store() -> Dict[str, Any]:
    with _lock:
        return _read_json(CHAT_STORE, {"conversations": [], "messages": {}})


def save_chat_store(store: Dict[str, Any]) -> None:
    with _lock:
        _write_json(CHAT_STORE, store)


def load_file_registry() -> Dict[str, Any]:
    with _lock:
        return _read_json(FILE_REGISTRY, {"files": {}})


def save_file_registry(reg: Dict[str, Any]) -> None:
    with _lock:
        _write_json(FILE_REGISTRY, reg)


def get_active_llm_settings() -> Dict[str, Any]:
    cfg = load_runtime_config()
    provider = cfg.get("provider") or "demo"
    keys = cfg.get("apiKeys") or {}
    models = cfg.get("models") or {}
    return {
        "provider": provider,
        # strip：避免用户复制密钥时带入换行/空格，导致 httpx 报非法 header value
        "api_key": (keys.get(provider) or "").strip(),
        "base_url": (_base_url_for(provider, keys) or "").strip() or None,
        "model": (models.get(provider) or _default_model(provider) or "").strip(),
        "temperature": float(cfg.get("temperature") or 0.7),
    }


def _base_url_for(provider: str, keys: Dict[str, Any]) -> Optional[str]:
    """解析 base_url：用户自定义优先，否则取厂商官方默认。

    统一走 `core.providers` 注册表 —— 此前本项目在 llm_client.py(2处)、
    persist.py、api_routes.py 各写一份且互相矛盾，是"配置成功却调用失败"的温床。
    """
    spec = get_provider(provider)
    if provider == "local":
        user_url = keys.get("localUrl") or keys.get("localBase")
    else:
        user_url = keys.get(f"{provider}Base")  # 兼容历史字段：dashscopeBase 等
    resolved = resolve_base_url(provider, user_url)
    return resolved or None


def _default_model(provider: str) -> str:
    """兜底模型名 —— 唯一真源是 `core.providers` 注册表。

    重要教训（记录在案以免重犯）：厂商模型迭代极快，硬编码猜测的代价本项目
    已经付过两次 —— 一次把**真实存在**的 `deepseek-v4-pro` 判为"不存在的模型"；
    一次把**已退役**的 `deepseek-chat`（2026-07-24 停止服务）当作推荐值。
    因此此处的取值仅用于"实时列表拉取失败"的最后兜底，
    正常路径必须调用 `GET /api/llm/models/live` 用用户自己的 Key 向厂商查询。
    """
    return get_provider(provider).default_model


def get_provider_runtime(provider: str) -> Dict[str, Any]:
    """供课件生成栈（services.llm）读取：与设置页 runtime_config.json 一致。"""
    cfg = load_runtime_config() or {}
    keys = cfg.get("apiKeys") or {}
    models = cfg.get("models") or {}
    active = cfg.get("provider") or "demo"
    key = (keys.get(provider) or "").strip()
    return {
        "api_key": key or None,
        "base_url": _base_url_for(provider, keys),
        "model": models.get(provider) or _default_model(provider),
        "temperature": float(cfg.get("temperature") or 0.7),
        "is_active": active == provider,
    }
