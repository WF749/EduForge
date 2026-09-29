"""教学工作流状态（Workflow）—— 从"提需求"到"出产物"的状态机。

与 `DialogueState` 的关系：**新增 + 映射，绝不替换**
--------------------------------------------------
`services/dialogue_manager.py` 的 `DialogueState` 是**通用对话状态机**
（初始 / 澄清 / 确认 / 执行 / 完成），它继续服务"含糊诉求"那条链路，
一行都不动。

教学工作流要表达的状态更多（还要区分"意图已形成""蓝图已生成""质检中""失败"），
因此**另立一套 `WorkflowState`，并与 `DialogueState` 做双向映射**：

    collecting   ↔ INITIAL
    clarifying   ↔ CLARIFYING
    intent_ready / blueprint_ready / awaiting_confirmation ↔ CONFIRMING
    generating   ↔ EXECUTING
    reviewing    ↔ REVIEWING   （DialogueState 新增，仅追加不改动原有成员）
    completed    ↔ COMPLETED
    failed       ↔ FAILED      （同上）

映射未知值一律回落到 INITIAL，**不抛异常** —— 老数据、脏数据都能加载。

刷新恢复
--------
`generating` / `reviewing` 在恢复时降级为 `failed(recoverable=True)`：
沿用既有 store 的"running 不恢复"约定，否则会永久转圈。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "WorkflowState", "Workflow",
    "to_dialogue_state", "from_dialogue_state",
    "can_transition", "normalize_workflow", "STAGE_LABELS",
]


class WorkflowState:
    """教学工作流状态（字符串常量，便于 JSON 序列化与前端直接比较）。"""

    COLLECTING = "collecting"                      # 收集需求
    CLARIFYING = "clarifying"                      # 补充关键信息（一次最多问一个）
    INTENT_READY = "intent_ready"                  # 教学意图已形成
    BLUEPRINT_READY = "blueprint_ready"            # 蓝图已生成
    AWAITING_CONFIRMATION = "awaiting_confirmation"  # 等待教师确认
    GENERATING = "generating"                      # 正在生成产物
    REVIEWING = "reviewing"                        # 质量检查中
    COMPLETED = "completed"                        # 生成完成
    FAILED = "failed"                              # 失败但可恢复

    ALL: Tuple[str, ...] = (
        COLLECTING, CLARIFYING, INTENT_READY, BLUEPRINT_READY,
        AWAITING_CONFIRMATION, GENERATING, REVIEWING, COMPLETED, FAILED,
    )


STAGE_LABELS: Dict[str, str] = {
    WorkflowState.COLLECTING: "正在理解您的需求",
    WorkflowState.CLARIFYING: "还差一点关键信息",
    WorkflowState.INTENT_READY: "教学意图已识别",
    WorkflowState.BLUEPRINT_READY: "教学蓝图已生成",
    WorkflowState.AWAITING_CONFIRMATION: "等待您确认",
    WorkflowState.GENERATING: "正在生成产物",
    WorkflowState.REVIEWING: "正在做质量检查",
    WorkflowState.COMPLETED: "生成完成",
    WorkflowState.FAILED: "生成失败",
}


# ---- 与 DialogueState 的双向映射 ------------------------------------------
# 只追加、不改动 dialogue_manager.DialogueState 的原有成员。
_TO_DIALOGUE: Dict[str, str] = {
    WorkflowState.COLLECTING: "initial",
    WorkflowState.CLARIFYING: "clarifying",
    WorkflowState.INTENT_READY: "confirming",
    WorkflowState.BLUEPRINT_READY: "confirming",
    WorkflowState.AWAITING_CONFIRMATION: "confirming",
    WorkflowState.GENERATING: "executing",
    WorkflowState.REVIEWING: "reviewing",
    WorkflowState.COMPLETED: "completed",
    WorkflowState.FAILED: "failed",
}

_FROM_DIALOGUE: Dict[str, str] = {
    "initial": WorkflowState.COLLECTING,
    "clarifying": WorkflowState.CLARIFYING,
    "confirming": WorkflowState.AWAITING_CONFIRMATION,
    "executing": WorkflowState.GENERATING,
    "reviewing": WorkflowState.REVIEWING,
    "completed": WorkflowState.COMPLETED,
    "failed": WorkflowState.FAILED,
}


def to_dialogue_state(state: str) -> str:
    """工作流状态 → 对话状态。未知值回落 initial（不抛异常）。"""
    return _TO_DIALOGUE.get(state, "initial")


def from_dialogue_state(state: str) -> str:
    """对话状态 → 工作流状态。未知值回落 collecting（不抛异常）。"""
    return _FROM_DIALOGUE.get(state, WorkflowState.COLLECTING)


# ---- 允许的迁移 -----------------------------------------------------------
# 设计取向：**松**。教学流程常被用户打断（改需求、跳蓝图、重试），
# 过度严格的迁移表会把正常操作判成非法，于是这里只禁止明显倒流的组合。
_ALLOWED: Dict[str, Tuple[str, ...]] = {
    WorkflowState.COLLECTING: (
        WorkflowState.CLARIFYING, WorkflowState.INTENT_READY,
        WorkflowState.GENERATING, WorkflowState.FAILED,
    ),
    WorkflowState.CLARIFYING: (
        WorkflowState.COLLECTING, WorkflowState.INTENT_READY,
        WorkflowState.GENERATING, WorkflowState.FAILED,
    ),
    WorkflowState.INTENT_READY: (
        WorkflowState.CLARIFYING, WorkflowState.BLUEPRINT_READY,
        WorkflowState.GENERATING, WorkflowState.COLLECTING,
    ),
    WorkflowState.BLUEPRINT_READY: (
        WorkflowState.AWAITING_CONFIRMATION, WorkflowState.GENERATING,
        WorkflowState.COLLECTING, WorkflowState.FAILED,
    ),
    WorkflowState.AWAITING_CONFIRMATION: (
        WorkflowState.GENERATING, WorkflowState.BLUEPRINT_READY,
        WorkflowState.COLLECTING,
    ),
    WorkflowState.GENERATING: (
        WorkflowState.REVIEWING, WorkflowState.COMPLETED,
        WorkflowState.FAILED,
    ),
    WorkflowState.REVIEWING: (
        WorkflowState.COMPLETED, WorkflowState.FAILED,
        WorkflowState.GENERATING,
    ),
    WorkflowState.COMPLETED: (
        WorkflowState.COLLECTING, WorkflowState.GENERATING,
    ),
    # failed 必须可恢复：任何"回到收集"或"重试"都要允许
    WorkflowState.FAILED: (
        WorkflowState.COLLECTING, WorkflowState.GENERATING,
        WorkflowState.BLUEPRINT_READY, WorkflowState.CLARIFYING,
    ),
}


def can_transition(from_state: str, to_state: str) -> bool:
    """是否允许迁移。未知状态一律允许（避免老数据被卡死）。"""
    if from_state not in _ALLOWED or to_state not in WorkflowState.ALL:
        return True
    if from_state == to_state:
        return True
    return to_state in _ALLOWED[from_state]


@dataclass
class Workflow:
    """工作流状态快照。字段都有默认值：老数据缺字段也能安全构造。"""
    state: str = WorkflowState.COLLECTING
    pendingQuestion: str = ""
    missingFields: List[str] = field(default_factory=list)
    activeKinds: List[str] = field(default_factory=list)
    # {stage, index, total, message}
    progress: Dict[str, Any] = field(default_factory=dict)
    # {stage, message, recoverable}
    lastError: Dict[str, Any] = field(default_factory=dict)
    # 与 DialogueManager 共用同一会话时的影子状态（只追加，不替换）
    dialogueState: str = "initial"
    updatedAt: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "pendingQuestion": self.pendingQuestion,
            "missingFields": list(self.missingFields),
            "activeKinds": list(self.activeKinds),
            "progress": dict(self.progress or {}),
            "lastError": dict(self.lastError or {}),
            "dialogueState": self.dialogueState,
            "updatedAt": self.updatedAt,
        }


def _safe_int(v: Any, default: int = 0) -> int:
    """同上：工作流状态来自前端与台账，脏数据不能让它抛异常。"""
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, str):
        try:
            return int(float(v.strip()))
        except (TypeError, ValueError):
            return default
    return default


def _clean_str(v: Any, limit: int = 200) -> str:
    if v is None:
        return ""
    if not isinstance(v, str):
        return ""
    return " ".join(v.split())[:limit]


def _clean_list(v: Any, limit: int = 20) -> List[str]:
    if not isinstance(v, (list, tuple)):
        return []
    out: List[str] = []
    for it in v[:limit]:
        s = _clean_str(it, 60)
        if s and s not in out:
            out.append(s)
    return out


def normalize_workflow(payload: Any = None, *, restore: bool = False) -> Workflow:
    """宽容解析工作流状态。

    `restore=True`（刷新恢复）时把 `generating` / `reviewing` 降级成
    `failed(recoverable=True)` —— 沿用既有约定：进程早没了，
    恢复成"进行中"会永久转圈。
    """
    src = payload if isinstance(payload, dict) else {}

    state = _clean_str(src.get("state"), 30)
    if state not in WorkflowState.ALL:
        state = WorkflowState.COLLECTING

    wf = Workflow(
        state=state,
        pendingQuestion=_clean_str(src.get("pendingQuestion"), 300),
        missingFields=_clean_list(src.get("missingFields")),
        activeKinds=_clean_list(src.get("activeKinds")),
        progress=dict(src.get("progress") or {}) if isinstance(
            src.get("progress"), dict) else {},
        lastError=dict(src.get("lastError") or {}) if isinstance(
            src.get("lastError"), dict) else {},
        dialogueState=_clean_str(src.get("dialogueState"), 20) or "initial",
        updatedAt=_safe_int(src.get("updatedAt"), 0),
    )

    if restore and wf.state in (WorkflowState.GENERATING, WorkflowState.REVIEWING):
        wf.state = WorkflowState.FAILED
        wf.lastError = {
            "stage": "restore",
            "message": "上次生成被中断，请重新生成",
            "recoverable": True,
        }
        wf.progress = {}

    # 影子状态始终与 state 对齐，避免两边漂移
    wf.dialogueState = to_dialogue_state(wf.state)
    return wf


def transition(wf: Workflow, to_state: str, **patch: Any) -> Workflow:
    """迁移到新状态。非法迁移**不抛异常**，只忽略并保留原状态 ——
    状态机出错不该让备课流程崩掉。
    """
    if not can_transition(wf.state, to_state):
        return wf
    wf.state = to_state
    wf.dialogueState = to_dialogue_state(to_state)
    for k, v in patch.items():
        if hasattr(wf, k):
            setattr(wf, k, v)
    return wf


def label(state: str) -> str:
    """给教师看的中文状态名。"""
    return STAGE_LABELS.get(state, "进行中")


def missing_field_labels(wf: Optional[Workflow]) -> List[str]:
    return list((wf.missingFields if wf else None) or [])
