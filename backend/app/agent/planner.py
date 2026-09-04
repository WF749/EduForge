"""Planner —— 任务拆解与规划。

核心设计：不为了"看起来有规划"而过度拆解
------------------------------------------
很多 Agent 项目把每个问题都拆成 5-8 步，结果是：简单问题也要调 3 次模型，
又慢又贵又容易出错。本实现做了**复杂度分级**：

  - 闲聊 / 简单问答     → 0 个工具步骤，直接回答
  - 需要查资料          → 检索 + 回答（2 步）
  - 需要产出教案/课件   → 检索 → 生成 → 校验（3-4 步）

LLM 负责生成计划，但我们用规则兜底：
  - 解析失败 → 退化为"直接回答"，不阻塞用户；
  - 步骤数超上限 → 截断；
  - 引用了不存在的工具 → 丢弃该步骤。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..core.logging_setup import get_logger
from ..core.llm_gateway import llm_chat, llm_chat_json
from .context import AgentContext
from .tools.base import registry

log = get_logger("agent.planner")

MAX_STEPS = 6

PLAN_SYSTEM = """你是一个教学备课助手的任务规划器。
把用户的目标拆解为有序的执行步骤，每步最多调用一个工具，或不需要工具（直接思考/写作）。

可用工具：
{tools}

输出**严格**的 JSON，格式如下，不要有任何额外文字或代码块标记：
{{
  "need_tools": true/false,
  "goal_type": "chat|qa|generate|research",
  "steps": [
    {{"description": "这一步要做什么（中文，一句话）", "tool": "工具名或 null", "args": {{}}}}
  ]
}}

规则：
1. 简单闲聊、概念解释 → need_tools=false，steps 只留 1 步且 tool=null。
2. 需要依据资料回答 → 先用 knowledge_search 检索，再回答。
3. 要生成教案/课件/习题 → 检索（可选）→ 生成 → 校验，共 2-3 步。
4. 步骤总数不超过 {max_steps} 步。
5. args 里的参数名必须与工具定义的参数名一致，值必须是字符串或数字。
"""


@dataclass
class PlanStep:
    id: int
    description: str
    tool: Optional[str] = None
    args: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[int] = field(default_factory=list)
    # 运行时状态
    done: bool = False
    result: Any = None
    error: str = ""
    attempts: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "description": self.description, "tool": self.tool,
            "args": self.args, "depends_on": self.depends_on,
            "done": self.done, "error": self.error, "attempts": self.attempts,
        }


class Planner:
    """生成并校验执行计划。"""

    def __init__(self, max_steps: int = MAX_STEPS) -> None:
        self.max_steps = max_steps

    def plan(self, goal: str, ctx: AgentContext) -> List[PlanStep]:
        """返回计划；任何异常都退化为"直接回答"，保证用户永远拿得到响应。"""
        tools_desc = registry.describe_for_prompt()
        prompt = (
            PLAN_SYSTEM.format(tools=tools_desc or "（无可用工具）", max_steps=self.max_steps)
            + f"\n\n用户长期偏好：{json.dumps(ctx.memory, ensure_ascii=False) if ctx.memory else '无'}\n"
            + f"用户目标：{goal}"
        )

        try:
            raw = llm_chat_json(prompt, purpose="planner", temperature=0.2, max_tokens=800)
            steps = self._validate(raw, goal)
            if steps:
                log.info("规划出 %d 步：%s", len(steps), [s.tool for s in steps])
                return steps
        except Exception as e:
            # 规划失败不是致命错误 —— 退化为直接回答，绝不阻塞用户
            log.warning("任务规划失败，退化为直接回答: %s", e)

        return [PlanStep(id=1, description="直接回答用户问题", tool=None)]

    def _validate(self, raw: Any, goal: str) -> List[PlanStep]:
        """校验 LLM 产出的计划，剔除非法步骤。"""
        if not isinstance(raw, dict):
            return []
        if raw.get("need_tools") is False:
            return [PlanStep(id=1, description="直接回答用户问题", tool=None)]

        raw_steps = raw.get("steps")
        if not isinstance(raw_steps, list) or not raw_steps:
            return []

        steps: List[PlanStep] = []
        for i, s in enumerate(raw_steps[: self.max_steps], 1):
            if not isinstance(s, dict):
                continue
            desc = str(s.get("description") or "").strip()
            if not desc:
                continue
            tool = s.get("tool")
            tool = str(tool).strip() if tool and str(tool).strip().lower() != "null" else None
            args = s.get("args") or {}
            if not isinstance(args, dict):
                args = {}

            # 引用了不存在的工具 → 降级为纯思考步骤，而不是让执行器崩掉
            if tool and registry.get(tool) is None:
                log.warning("计划引用了未注册的工具 %s，已降级为无工具步骤", tool)
                tool = None

            steps.append(PlanStep(
                id=i,
                description=desc,
                tool=tool,
                args=args,
                depends_on=[i - 1] if i > 1 else [],
            ))

        if not steps:
            return []
        return steps
