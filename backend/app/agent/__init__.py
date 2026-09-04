"""EduForge Agent 核心能力层。

按真实业务需要提供的能力：
  - context      分层上下文工程（不是简单存聊天记录）
  - planner      任务拆解与规划（简单任务不过度拆解）
  - executor     工具执行与失败恢复（重试 / 参数修正 / 工具替换 / 降级标记）
  - verifier     结果验证（规则 + 模型，产出定向修改意见）
  - orchestrator 编排（planner → researcher → writer → critic 按需登场）

刻意**不做**的事：
  - 不为了"看起来高级"堆砌常驻多 Agent 进程；
  - 不把简单问题拆成 8 步；
  - 不在失败时静默降级成编造内容。
"""

from .context import AgentContext, ContextBuilder, ToolCallRecord
from .executor import Executor, StepOutcome
from .orchestrator import AgentRunResult, Orchestrator, run_agent
from .planner import PlanStep, Planner
from .tools.base import RiskLevel, ToolResult, ToolSpec, registry
from .tools import builtin as _builtin  # noqa: F401  导入即注册内置工具
from .verifier import VerificationResult, Verifier

__all__ = [
    "AgentContext", "ContextBuilder", "ToolCallRecord",
    "Planner", "PlanStep",
    "Executor", "StepOutcome",
    "Verifier", "VerificationResult",
    "Orchestrator", "AgentRunResult", "run_agent",
    "registry", "ToolResult", "ToolSpec", "RiskLevel",
]
