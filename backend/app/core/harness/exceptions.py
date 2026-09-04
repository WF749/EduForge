"""Harness 层异常定义。

设计原则：任何模型调用失败都必须被如实暴露，禁止静默降级为编造内容。
这是企业级智能体与企业级玩具的分界线。
"""

from typing import Optional


class LLMError(Exception):
    """LLM 调用相关错误的基类。"""

    def __init__(
        self,
        message: str,
        *,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.model = model
        self.cause = cause


class LLMUnavailableError(LLMError):
    """模型不可用（配置缺失 / 限流 / 网络 / 鉴权失败）。

    调用方必须向用户如实展示，绝不返回 demo 模板或缓存的假内容来"假装成功"。
    """


class LLMTimeoutError(LLMError):
    """调用超过设定超时阈值。"""


class LLMProviderError(LLMError):
    """Provider 返回的业务错误（如 4xx / 5xx）。"""
