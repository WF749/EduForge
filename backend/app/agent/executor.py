"""Executor —— 执行引擎与失败恢复。

工具调用失败的恢复策略（逐级降级，不硬失败）
--------------------------------------------
1. **退避重试**：瞬时故障（网络抖动/限流）→ 等待 2^n 秒后重试，最多 2 次。
2. **参数修正**：若失败疑似参数问题（缺字段/类型不对），让 LLM 依据错误信息
   重新生成参数，再试一次。这比盲目重试有效得多。
3. **工具替换**：预定义等价工具（如 web_search 失败 → knowledge_search）。
4. **跳过并标记降级**：单步失败不影响全局时，跳过该步，但**必须**在最终结果里
   告知用户"哪一步没做成、为什么"。
5. **终止并如实报错**：关键步骤失败则停止，抛出带上下文的异常。

全程记录 attempt 次数，可在 /api/metrics 观察重试率。
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from ..core.errors import ErrorCode, HumanApprovalRequired
from ..core.logging_setup import get_logger
from ..core.observability import Span, metrics
from .context import AgentContext, ToolCallRecord, summarize_tool_output
from .planner import PlanStep
from .tools.base import RiskLevel, ToolResult, registry

log = get_logger("agent.executor")

# 等价工具：主工具失败时可尝试的替代方案
FALLBACKS: Dict[str, List[str]] = {
    "web_search": ["knowledge_search"],
    "knowledge_search": ["web_search"],
    "generate_courseware": ["generate_lesson_plan"],
}

MAX_ATTEMPTS = 3


class StepOutcome:
    """一步的执行结果。"""

    def __init__(self, step: PlanStep, ok: bool, result: Any = None,
                 error: str = "", degraded: bool = False, skipped: bool = False):
        self.step = step
        self.ok = ok
        self.result = result
        self.error = error
        self.degraded = degraded
        self.skipped = skipped

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step.to_dict(),
            "ok": self.ok,
            "degraded": self.degraded,
            "skipped": self.skipped,
            "error": self.error,
        }


class Executor:
    """按计划执行工具调用，带完整恢复链路。"""

    def __init__(
        self,
        *,
        on_approval_required: Optional[Callable[[str, Dict[str, Any]], bool]] = None,
        on_progress: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ):
        # 高风险工具的确认回调；返回 True 才执行。默认一律拒绝（安全优先）
        self._approve = on_approval_required or (lambda name, args: False)
        self._progress = on_progress or (lambda *a, **k: None)

    # ------------------------------------------------------------------

    def run(self, ctx: AgentContext, steps: List[PlanStep]) -> List[StepOutcome]:
        outcomes: List[StepOutcome] = []

        for i, step in enumerate(steps):
            ctx.current_step = i
            self._progress("step_start", {"step": step.to_dict()})

            if not step.tool:
                # 纯思考/写作步骤，无工具调用
                step.done = True
                outcomes.append(StepOutcome(step, ok=True))
                continue

            outcome = self._run_tool_step(ctx, step)
            step.done = outcome.ok
            step.attempts = getattr(step, "attempts", 0)
            outcomes.append(outcome)

            self._progress("step_done", outcome.to_dict())

            # 关键步骤失败 → 终止，避免带着错误信息继续生成
            if not outcome.ok and self._is_critical(step):
                log.error("关键步骤 %s 失败，终止执行: %s", step.tool, outcome.error)
                break

        return outcomes

    def _is_critical(self, step: PlanStep) -> bool:
        """生成类步骤失败后继续没有意义，判定为关键步骤。"""
        return bool(step.tool and step.tool.startswith("generate_"))

    # ------------------------------------------------------------------

    def _run_tool_step(self, ctx: AgentContext, step: PlanStep) -> StepOutcome:
        tool_name = step.tool or ""
        args = dict(step.args or {})
        last_error = ""
        attempt = 1

        while attempt <= MAX_ATTEMPTS:
            step.attempts = attempt
            result = registry.execute(tool_name, args, attempt=attempt,
                                      approved=self._maybe_approve(tool_name, args))

            if result.ok:
                self._record(ctx, tool_name, args, result)
                step.result = result.data
                return StepOutcome(step, ok=True, result=result.data,
                                   degraded=result.degraded)

            last_error = result.error
            err_code = result.error_code

            # 高风险未获批准：不重试，直接返回，交由上层请求人工确认
            if err_code == ErrorCode.HUMAN_APPROVAL_REQUIRED:
                return StepOutcome(step, ok=False, error=result.error, degraded=False)

            # 策略 2：参数问题 → 让 LLM 依据错误信息修正参数
            if attempt == 1 and self._looks_like_arg_error(result.error):
                fixed = self._fix_args(tool_name, args, result.error, ctx)
                if fixed:
                    log.info("工具 %s 参数已修正，重试", tool_name)
                    args = fixed
                    attempt += 1
                    time.sleep(0.5)
                    continue

            # 策略 1：退避重试
            if attempt < MAX_ATTEMPTS:
                wait = 2 ** (attempt - 1)
                log.warning("工具 %s 第 %d 次失败，%ss 后重试: %s", tool_name, attempt, wait, result.error)
                time.sleep(wait)
                attempt += 1
                continue
            break

        # 策略 3：等价工具替换
        for alt in FALLBACKS.get(tool_name, []):
            if ctx.tool_used(alt):
                continue
            log.info("工具 %s 最终失败，尝试等价工具 %s", tool_name, alt)
            alt_res = registry.execute(alt, step.args or {}, attempt=MAX_ATTEMPTS,
                                       approved=self._maybe_approve(alt, step.args or {}))
            if alt_res.ok:
                self._record(ctx, alt, step.args or {}, alt_res)
                step.tool = alt
                step.result = alt_res.data
                return StepOutcome(step, ok=True, result=alt_res.data,
                                   degraded=True,
                                   error=f"原工具 {tool_name} 失败，已改用 {alt}")
            last_error = f"{last_error}；替代工具 {alt} 也失败：{alt_res.error}"

        # 策略 4/5：交给上层决定（跳过或终止）
        return StepOutcome(step, ok=False, error=last_error or "未知错误")

    # ------------------------------------------------------------------

    def _maybe_approve(self, tool_name: str, args: Dict[str, Any]) -> bool:
        spec = registry.get(tool_name)
        if not spec or spec.risk != RiskLevel.HIGH:
            return False  # 非高风险不需要批准标记
        approved = self._approve(tool_name, args)
        log.warning("高风险工具 %s 审批结果: %s", tool_name, "批准" if approved else "拒绝")
        return approved

    def _looks_like_arg_error(self, error: str) -> bool:
        low = (error or "").lower()
        markers = [
            "missing", "required", "unexpected", "argument", "参数",
            "typeerror", "got an unexpected", "invalid", "不合法", "不能为空",
        ]
        return any(m in low for m in markers)

    def _fix_args(self, tool_name: str, args: Dict[str, Any], error: str, ctx: AgentContext) -> Optional[Dict[str, Any]]:
        """让 LLM 依据报错修正工具参数。

        修正失败返回 None，由调用方继续走重试/替换流程。
        """
        spec = registry.get(tool_name)
        if not spec:
            return None
        from ..core.llm_gateway import llm_chat_json

        prompt = (
            "调用工具时参数有误，请修正后重新给出参数。\n\n"
            f"工具名：{tool_name}\n"
            f"工具说明：{spec.description}\n"
            f"参数 Schema：{spec.parameters}\n"
            f"上次传入的参数：{args}\n"
            f"报错信息：{error}\n\n"
            "只输出修正后的参数 JSON，键名必须与 Schema 一致，不要任何解释文字。"
        )
        try:
            fixed = llm_chat_json(prompt, purpose="fix_tool_args", temperature=0.0, max_tokens=400)
            if isinstance(fixed, dict):
                # 只保留 Schema 中声明的字段，避免模型塞入幻觉参数
                allowed = set((spec.parameters or {}).get("properties", {}).keys())
                return {k: v for k, v in fixed.items() if k in allowed}
        except Exception as e:
            log.warning("参数修正失败: %s", e)
        return None

    def _record(self, ctx: AgentContext, tool: str, args: Dict[str, Any], result: ToolResult) -> None:
        summary = summarize_tool_output(tool, result.data)
        ctx.add_tool_call(ToolCallRecord(
            tool=tool,
            args={k: (str(v)[:80] if not isinstance(v, (int, float, bool)) else v) for k, v in args.items()},
            ok=result.ok,
            summary=summary,
            full="" if isinstance(result.data, str) else str(result.data)[:4000],
        ))
        # 检索类结果同时注入知识层，供后续生成引用
        if tool in ("knowledge_search", "web_search") and isinstance(result.data, list):
            ctx.add_knowledge([
                {"content": str(x.get("content", x))[:1200], "source": str(x.get("source", tool))}
                for x in result.data if isinstance(x, (dict, str))
            ])
