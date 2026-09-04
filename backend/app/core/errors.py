"""统一错误体系与全局异常处理。

目标
----
1. **错误可被机器识别**：每个业务异常带稳定 `code`，前端可据此做分支处理，
   而不是靠匹配中文错误文案（文案一改就失效）。
2. **错误对用户有意义**：`message` 直接可展示，指明"该做什么"而非只报技术细节。
3. **错误绝不静默**：任何降级都必须显式标记 `degraded`，禁止把失败伪装成成功。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .logging_setup import get_logger

log = get_logger("errors")


# ---------------------------------------------------------------------------
# 错误码（稳定契约，只增不改）
# ---------------------------------------------------------------------------

class ErrorCode:
    # 配置类 1xxx
    NO_PROVIDER = "E1001"          # 未选择厂商
    NO_API_KEY = "E1002"           # 未配置密钥
    INVALID_API_KEY = "E1003"      # 密钥无效（401）
    QUOTA_EXCEEDED = "E1004"       # 额度耗尽 / 限流（429）
    MODEL_NOT_FOUND = "E1005"      # 模型不存在（404）
    BAD_BASE_URL = "E1006"         # 地址不可达

    # 调用类 2xxx
    LLM_UNAVAILABLE = "E2001"      # 模型不可用
    LLM_TIMEOUT = "E2002"          # 超时
    LLM_BAD_RESPONSE = "E2003"     # 返回体无法解析
    CIRCUIT_OPEN = "E2004"         # 熔断中
    UNSUPPORTED_CAPABILITY = "E2005"  # 该厂商/模型不支持此能力（如视觉）

    # 业务类 3xxx
    INVALID_INPUT = "E3001"
    NOT_FOUND = "E3002"
    TOOL_FAILED = "E3003"
    VERIFICATION_FAILED = "E3004"  # 结果验证未通过
    HUMAN_APPROVAL_REQUIRED = "E3005"  # 高风险操作需人工确认
    DATA_EGRESS_BLOCKED = "E3006"      # 敏感数据外发被安全策略阻断

    # 系统类 9xxx
    INTERNAL = "E9001"


class AppError(Exception):
    """所有业务异常的基类。"""

    code: str = ErrorCode.INTERNAL
    status: int = 500
    hint: str = ""

    def __init__(
        self,
        message: str,
        *,
        code: Optional[str] = None,
        status: Optional[int] = None,
        hint: Optional[str] = None,
        detail: Any = None,
        degraded: bool = False,
    ):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status:
            self.status = status
        if hint:
            self.hint = hint
        self.detail = detail
        self.degraded = degraded

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "success": False,
            "code": self.code,
            "message": self.message,
        }
        if self.hint:
            d["hint"] = self.hint
        if self.detail is not None:
            d["detail"] = self.detail
        if self.degraded:
            d["degraded"] = True
        return d


# ---- 具体异常 ------------------------------------------------------------

class ConfigError(AppError):
    code = ErrorCode.NO_PROVIDER
    status = 400


class AuthError(AppError):
    """密钥无效/过期/额度问题 —— 用户可自行修复。"""
    code = ErrorCode.INVALID_API_KEY
    status = 401
    hint = "请到「设置」页检查 API Key 是否正确、是否过期、余额是否充足。"


class QuotaError(AppError):
    code = ErrorCode.QUOTA_EXCEEDED
    status = 429
    hint = "请求过于频繁或额度已用尽，请稍后重试或更换模型。"


class ModelNotFoundError(AppError):
    code = ErrorCode.MODEL_NOT_FOUND
    status = 404
    hint = "可在设置页点击「拉取模型列表」获取该厂商当前可用的模型名。"


class LLMUnavailableError(AppError):
    code = ErrorCode.LLM_UNAVAILABLE
    status = 503
    hint = "请稍后重试，或在设置页切换其它厂商/模型。"


class LLMTimeoutError(AppError):
    code = ErrorCode.LLM_TIMEOUT
    status = 504
    hint = "生成耗时过长，可尝试换用更快的模型或缩短输入。"


class UnsupportedCapabilityError(AppError):
    code = ErrorCode.UNSUPPORTED_CAPABILITY
    status = 400


class ToolError(AppError):
    code = ErrorCode.TOOL_FAILED
    status = 500


class VerificationError(AppError):
    code = ErrorCode.VERIFICATION_FAILED
    status = 422


class HumanApprovalRequired(AppError):
    """高风险操作（发送邮件/提交审批/资金操作）需人工确认。"""
    code = ErrorCode.HUMAN_APPROVAL_REQUIRED
    status = 409
    hint = "该操作风险较高，需人工确认后才会执行。"


class DataEgressBlockedError(AppError):
    """输入含敏感数据且目标为云端，按当前安全策略被阻断。

    注意：这是**主动拦截**，不是故障。提示必须告诉用户怎么绕过
    （换校内模型 / 移除敏感信息），否则只会让人卡住。
    """
    code = ErrorCode.DATA_EGRESS_BLOCKED
    status = 403
    hint = "请改用校内/内网模型，或移除其中的个人信息后重试。"


# ---------------------------------------------------------------------------
# 全局异常处理
# ---------------------------------------------------------------------------

def install_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器，保证任何路径都返回结构化 JSON。"""

    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        log.warning("业务异常 %s: %s", exc.code, exc.message)
        return JSONResponse(status_code=exc.status, content=exc.to_dict())

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "code": ErrorCode.NOT_FOUND if exc.status_code == 404 else ErrorCode.INTERNAL,
                "message": str(exc.detail),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        # 只回传字段位置与原因，不透传用户输入内容（避免敏感信息回显）
        errors = [
            {"field": ".".join(str(p) for p in e.get("loc", [])[1:]), "reason": e.get("msg", "")}
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "code": ErrorCode.INVALID_INPUT,
                "message": "请求参数不合法",
                "detail": errors,
            },
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.exception("未捕获异常 @ %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "code": ErrorCode.INTERNAL,
                "message": f"服务内部错误：{type(exc).__name__}",
                "hint": "详细堆栈已写入服务端日志。",
            },
        )
