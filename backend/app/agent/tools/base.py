"""工具（Tool）抽象与注册表 —— Agent 的"手"。

设计要点
--------
1. **声明即契约**：工具的 JSON Schema 由 Python 类型注解自动生成，
   保证"给模型看的描述"和"实际执行的签名"永远一致，不会出现模型调用参数对不上。
2. **结果结构化**：ToolResult 带 `ok / degraded / error_code`，
   失败不会静默变成空字符串——执行器据此决定重试/换工具/降级。
3. **风险分级**：`risk` 字段标记工具危险等级，高风险工具（发送、提交、支付）
   必须经人工确认才能执行，这是"人机协同"的落点。
"""

from __future__ import annotations

import inspect
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, get_type_hints

from ...core.errors import ErrorCode
from ...core.logging_setup import get_logger
from ...core.observability import Span, metrics

log = get_logger("agent.tools")


class RiskLevel(str, Enum):
    SAFE = "safe"            # 只读，可直接执行
    MODERATE = "moderate"    # 会写本地文件/生成产物，可自动执行但需记录
    HIGH = "high"            # 外部副作用：发送邮件、提交审批、支付 —— 必须人工确认


@dataclass
class ToolResult:
    """工具执行结果。"""

    ok: bool
    data: Any = None
    error: str = ""
    error_code: str = ""
    # 降级标记：工具没完全失败，但产出的是次优结果（如检索为空、回退到缓存）
    degraded: bool = False
    degrade_reason: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success(cls, data: Any, **meta) -> "ToolResult":
        return cls(ok=True, data=data, meta=meta)

    @classmethod
    def failure(cls, error: str, code: str = ErrorCode.TOOL_FAILED) -> "ToolResult":
        return cls(ok=False, error=error, error_code=code)

    @classmethod
    def partial(cls, data: Any, reason: str, **meta) -> "ToolResult":
        """降级成功：有结果但不完整，必须告知调用方。"""
        return cls(ok=True, data=data, degraded=True, degrade_reason=reason, meta=meta)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "data": self.data,
            "error": self.error,
            "error_code": self.error_code,
            "degraded": self.degraded,
            "degrade_reason": self.degrade_reason,
            "meta": self.meta,
        }

    def __str__(self) -> str:
        if self.ok:
            return str(self.data)
        return f"[{self.error_code}] {self.error}"


@dataclass
class ToolSpec:
    """一个工具的元数据。"""

    name: str
    description: str
    func: Callable[..., Any]
    parameters: Dict[str, Any]          # JSON Schema
    risk: RiskLevel = RiskLevel.SAFE
    requires_llm: bool = False          # 是否内部需要调 LLM（影响成本控制）
    timeout_s: float = 60.0
    category: str = "general"
    examples: List[str] = field(default_factory=list)

    def openai_schema(self) -> Dict[str, Any]:
        """转成 OpenAI function-calling 格式。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


_PY_TO_JSON: Dict[type, str] = {
    str: "string", int: "integer", float: "number", bool: "boolean",
    list: "array", dict: "object",
}


def _schema_from_signature(func: Callable) -> Dict[str, Any]:
    """从类型注解生成 JSON Schema，杜绝描述与实现脱节。"""
    try:
        hints = get_type_hints(func)
    except Exception:
        hints = {}
    sig = inspect.signature(func)
    props: Dict[str, Any] = {}
    required: List[str] = []

    for pname, param in sig.parameters.items():
        if pname in ("self", "cls"):
            continue
        ann = hints.get(pname, str)
        json_type = _PY_TO_JSON.get(ann, "string")
        # 支持 Optional[X] -> X 且非必填
        origin = getattr(ann, "__origin__", None)
        optional = False
        if str(ann).startswith("typing.Optional"):
            optional = True
            args = getattr(ann, "__args__", ())
            if args:
                inner = args[0]
                json_type = _PY_TO_JSON.get(inner, "string")
        if param.default is inspect.Parameter.empty and not optional:
            required.append(pname)

        desc = ""
        if param.default is not inspect.Parameter.empty and isinstance(param.default, str):
            # 约定：字符串默认值可携带 "说明" 形式不再解析，保持简单
            pass
        props[pname] = {"type": json_type}
        if desc:
            props[pname]["description"] = desc

    return {"type": "object", "properties": props, "required": required}


def _coerce_scalar(value: Any, target: str) -> Any:
    """把单个值转换为 Schema 声明的类型。"""
    if target == "string":
        if isinstance(value, (list, tuple)):
            return ",".join(str(v) for v in value)
        if isinstance(value, dict):
            import json as _json
            return _json.dumps(value, ensure_ascii=False)
        return value if isinstance(value, str) else str(value)
    if target == "integer":
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            s = value.strip()
            if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
                return int(s)
        return value
    if target == "number":
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
        if isinstance(value, str):
            try:
                return float(value.strip())
            except ValueError:
                return value
        return value
    if target == "boolean":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ("true", "1", "yes", "是")
        return bool(value)
    if target == "array":
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        return [value]
    if target == "object":
        return value if isinstance(value, dict) else {"value": value}
    return value


class ToolRegistry:
    """工具注册表：Agent 可用工具的唯一入口。"""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolSpec] = {}

    def register(
        self,
        name: str,
        description: str,
        *,
        risk: RiskLevel = RiskLevel.SAFE,
        requires_llm: bool = False,
        timeout_s: float = 60.0,
        category: str = "general",
        examples: Optional[List[str]] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        """装饰器方式注册工具。"""
        def deco(func: Callable) -> Callable:
            schema = parameters or _schema_from_signature(func)
            self._tools[name] = ToolSpec(
                name=name,
                description=description,
                func=func,
                parameters=schema,
                risk=risk,
                requires_llm=requires_llm,
                timeout_s=timeout_s,
                category=category,
                examples=examples or [],
            )
            return func
        return deco

    def get(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    def names(self) -> List[str]:
        return list(self._tools)

    def schemas(self, categories: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        tools = self._tools.values()
        if categories:
            tools = [t for t in tools if t.category in categories]
        return [t.openai_schema() for t in tools]

    def describe_for_prompt(self, categories: Optional[List[str]] = None) -> str:
        """给不支持 function-calling 的模型用的文本版工具清单。"""
        tools = list(self._tools.values())
        if categories:
            tools = [t for t in tools if t.category in categories]
        lines = []
        for t in tools:
            params = ", ".join(t.parameters.get("properties", {}).keys())
            lines.append(f"- {t.name}({params}): {t.description}")
        return "\n".join(lines)

    @staticmethod
    def _coerce_args(spec: "ToolSpec", args: Dict[str, Any]) -> Dict[str, Any]:
        """按 Schema 强制转换参数类型。

        为什么需要：LLM 生成的参数常常"意思对但类型不对" ——
        例如把 `question_types` 写成数组 `["选择","填空"]` 而 Schema 声明为 string；
        把 `top_k` 写成 `"5"` 而 Schema 声明为 integer。
        不做转换就会在工具内部抛 AttributeError（本项目实测踩到过）。

        同时剔除 Schema 未声明的字段，防止模型塞入幻觉参数。
        """
        props: Dict[str, Any] = (spec.parameters or {}).get("properties", {})
        if not props:
            return args

        coerced: Dict[str, Any] = {}
        for key, value in args.items():
            if key not in props:
                log.warning("工具 %s 收到未声明参数 %s，已忽略", spec.name, key)
                continue
            target = props[key].get("type", "string")
            try:
                coerced[key] = _coerce_scalar(value, target)
            except Exception:
                # 转换失败就原样传入，让工具自己给出更准确的错误
                coerced[key] = value
        return coerced

    def execute(
        self,
        name: str,
        args: Optional[Dict[str, Any]] = None,
        *,
        attempt: int = 1,
        approved: bool = False,
    ) -> ToolResult:
        """执行工具，统一计时、记录指标、捕获异常。

        高风险工具在 `approved=False` 时拒绝执行 —— 这是人机协同的强制落点。
        """
        spec = self._tools.get(name)
        if not spec:
            return ToolResult.failure(f"未注册的工具: {name}", ErrorCode.TOOL_FAILED)

        if spec.risk == RiskLevel.HIGH and not approved:
            return ToolResult.failure(
                f"工具 {name} 属于高风险操作，需人工确认后才会执行",
                ErrorCode.HUMAN_APPROVAL_REQUIRED,
            )

        args = self._coerce_args(spec, args or {})
        span = Span(kind="tool", name=name, attempt=attempt, meta={"args_keys": sorted(args)})
        try:
            result = spec.func(**args)
            if not isinstance(result, ToolResult):
                result = ToolResult.success(result)
            span.finish("ok")
            if result.degraded:
                span.status = "degraded"
            metrics.record(span)
            return result
        except Exception as e:
            log.warning("工具 %s 执行失败 (第%d次): %s", name, attempt, e)
            span.finish("error", error=e)
            metrics.record(span)
            return ToolResult.failure(f"{type(e).__name__}: {e}", ErrorCode.TOOL_FAILED)


registry = ToolRegistry()
