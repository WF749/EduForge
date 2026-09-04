"""Orchestrator —— Agent 运行编排。

角色划分（按备课业务实际需要，不为炫技）
----------------------------------------
  planner    任务规划     —— 拆解步骤，决定用不用工具
  researcher 资料检索     —— 知识库 / 联网，产出带来源的参考资料
  writer     内容生成     —— 基于上下文产出教案/课件/答案
  critic     结果审查     —— 结构与质量校验，产出定向修改意见

这些角色**不是**常驻进程，而是按需调用的阶段：
简单问答只会走 planner → writer；只有生成类任务才会额外走 critic。
这样既保留了协作结构，又避免了"每个问题都跑一遍全链路"的浪费。
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ..core.logging_setup import get_logger, set_context
from ..core.observability import Span, metrics
from .context import AgentContext, ContextBuilder
from .executor import Executor, StepOutcome
from .planner import PlanStep, Planner
from .tools.base import registry
from .verifier import VerificationResult, Verifier

log = get_logger("agent.orchestrator")

WRITER_SYSTEM = """你是 EduForge（教铸），面向 K-12 教师的本地化多模态备课智能体。

行为准则：
1. 有参考资料时**必须基于资料作答**，并在关键处标注来源；资料不足时明确说明"资料中未涉及"。
2. 不编造事实、数据、课标条文。无法确认的内容要如实说"不确定"。
3. 面向真实课堂：给出的环节要可操作，包含教师活动、学生活动与时间分配。
4. 使用中文，条理清晰，避免过度客套。
5. 若上下文标记了降级（degraded），在回答末尾用一句话说明"本回答未依赖某项资料"。
"""

RESEARCH_SYSTEM = "你是教学资源研究员，负责判断当前任务需要哪些资料，并提炼要点。"


@dataclass
class AgentRunResult:
    goal: str
    answer: str
    plan: List[Dict[str, Any]] = field(default_factory=list)
    outcomes: List[Dict[str, Any]] = field(default_factory=list)
    verification: Optional[Dict[str, Any]] = None
    degraded: bool = False
    degrade_reasons: List[str] = field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    trace_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal, "answer": self.answer, "plan": self.plan,
            "outcomes": self.outcomes, "verification": self.verification,
            "degraded": self.degraded, "degrade_reasons": self.degrade_reasons,
            "tool_calls": self.tool_calls, "metrics": self.metrics,
            "trace_id": self.trace_id,
        }


class Orchestrator:
    """一次 Agent 运行的完整生命周期。"""

    def __init__(
        self,
        *,
        max_steps: int = 6,
        max_revisions: int = 1,
        enable_verification: bool = True,
        context_tokens: int = 6000,
        on_progress: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        on_approval_required: Optional[Callable[[str, Dict[str, Any]], bool]] = None,
    ):
        self.planner = Planner(max_steps=max_steps)
        self.executor = Executor(on_approval_required=on_approval_required,
                                 on_progress=on_progress)
        self.verifier = Verifier() if enable_verification else None
        self.builder = ContextBuilder(max_tokens=context_tokens)
        self.max_revisions = max_revisions
        self._progress = on_progress or (lambda *a, **k: None)

    # ------------------------------------------------------------------

    def run(
        self,
        goal: str,
        *,
        session_id: str = "",
        memory: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, str]]] = None,
        content_type: str = "general",
        grade: str = "",
        subject: str = "",
    ) -> AgentRunResult:
        trace_id = uuid.uuid4().hex[:16]
        set_context(agent_name="orchestrator", step_name="run", trace_id=trace_id)
        started = time.time()
        span = Span(kind="agent", name="orchestrator", meta={"goal": goal[:120]})

        ctx = AgentContext(
            session_id=session_id or "-",
            goal=goal,
            memory=dict(memory or {}),
        )
        if subject:
            ctx.remember("学科", subject)
        if grade:
            ctx.remember("年级", grade)
        for h in (history or [])[-8:]:
            ctx.add_message(h.get("role", "user"), h.get("content", ""))
        ctx.add_message("user", goal)

        degrade_reasons: List[str] = []

        try:
            # ---- 1. 规划 -------------------------------------------------
            self._progress("planning", {"goal": goal})
            steps: List[PlanStep] = self.planner.plan(goal, ctx)
            ctx.plan = [s.to_dict() for s in steps]
            self._progress("planned", {"steps": ctx.plan})

            # ---- 2. 执行 -------------------------------------------------
            outcomes: List[StepOutcome] = self.executor.run(ctx, steps)
            for o in outcomes:
                if not o.ok and o.error:
                    degrade_reasons.append(f"步骤「{o.step.description}」失败：{o.error}")
                elif o.degraded and o.error:
                    degrade_reasons.append(o.error)

            # ---- 3. 综合生成 ---------------------------------------------
            self._progress("writing", {})
            answer = self._write(ctx, content_type)

            # ---- 4. 验证 + 定向修改 ---------------------------------------
            verification: Optional[VerificationResult] = None
            if self.verifier and content_type in ("lesson_plan", "exercise", "courseware"):
                verification = self.verifier.verify(
                    goal, answer, content_type=content_type, grade=grade, subject=subject
                )
                revision = 0
                while not verification.passed and revision < self.max_revisions:
                    revision += 1
                    self._progress("revising", {"round": revision, "issues": verification.issues})
                    answer = self._revise(ctx, goal, answer, verification)
                    verification = self.verifier.verify(
                        goal, answer, content_type=content_type, grade=grade, subject=subject
                    )
                if not verification.passed:
                    degrade_reasons.append("质量校验未完全通过：" + "；".join(verification.issues[:3]))

            span.finish("ok")
            metrics.record(span)

            return AgentRunResult(
                goal=goal,
                answer=answer,
                plan=[s.to_dict() for s in steps],
                outcomes=[o.to_dict() for o in outcomes],
                verification=verification.to_dict() if verification else None,
                degraded=bool(degrade_reasons),
                degrade_reasons=degrade_reasons,
                tool_calls=[{"tool": r.tool, "ok": r.ok, "summary": r.summary} for r in ctx.tool_calls],
                metrics={
                    "duration_ms": round((time.time() - started) * 1000, 2),
                    "steps": len(steps),
                    "tool_calls": len(ctx.tool_calls),
                    "revisions": revision_count(verification),
                },
                trace_id=trace_id,
            )

        except Exception as e:
            span.finish("error", error=e)
            metrics.record(span)
            log.error("Agent 运行失败: %s", e)
            raise

    # ------------------------------------------------------------------

    def _write(self, ctx: AgentContext, content_type: str) -> str:
        """Writer 阶段：基于完整上下文产出回答。"""
        from ..core.llm_gateway import llm_chat, llm_stream

        system = WRITER_SYSTEM
        if content_type in ("lesson_plan", "courseware", "exercise"):
            system += "\n\n本次要求输出**结构化内容**，使用 Markdown 标题分节，不要输出多余寒暄。"

        messages = self.builder.build(ctx, system_prompt=system)
        # 最后一条是用户问题，其余作为历史
        history = messages[1:-1] if len(messages) > 1 else []
        prompt = messages[-1]["content"] if messages else ctx.goal

        return llm_chat(prompt, system=system, history=history,
                        purpose=f"writer:{content_type}")

    def _revise(self, ctx: AgentContext, goal: str, previous: str, v: VerificationResult) -> str:
        """Critic → Writer 定向修改（保留正确部分，不全量重生成）。"""
        from ..core.llm_gateway import llm_chat

        prompt = self.verifier.build_revision_prompt(goal, previous, v)
        return llm_chat(prompt, system=WRITER_SYSTEM, purpose="writer:revision")


def revision_count(v: Optional[VerificationResult]) -> int:
    return 0 if v is None else (0 if v.passed else 1)


# ---- 便捷入口 -------------------------------------------------------------

def run_agent(goal: str, **kw) -> AgentRunResult:
    return Orchestrator().run(goal, **kw)
