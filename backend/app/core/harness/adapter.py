"""适配器：把既有 LLMService（SQLite 配置 + 遗留 Provider 实例）桥接到 Harness。

这样 Phase 1 的迁移可以"渐进式"——先让 Harness 接管调用，再逐步替换底层 Provider，
无需一次性重写所有生成链路。
"""

from typing import Optional

from .base import WrappedProvider
from .manager import LLMManager


def build_manager_from_service(llm_service) -> LLMManager:
    """从既有 LLMService 单例构建 LLMManager。

    llm_service 需提供：
        .providers: Dict[str, legacy_provider_instance]
        .get_config(provider) -> Dict | None
        .get_active_provider() -> str
    """
    manager = LLMManager()
    active = llm_service.get_active_provider()

    for name, legacy in llm_service.providers.items():
        cfg = llm_service.get_config(name) or {}
        wrapped = WrappedProvider(
            legacy=legacy,
            name=name,
            api_key=cfg.get("api_key"),
            base_url=cfg.get("base_url"),
            model=cfg.get("model"),
        )
        manager.register(name, wrapped)

    if active in manager.list_providers():
        manager.set_default(active)
    return manager
