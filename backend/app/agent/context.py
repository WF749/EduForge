"""上下文工程 —— Agent 的"工作记忆"。

为什么不是"存聊天记录"
----------------------
把聊天记录原样塞进 prompt 有三个致命问题：
  1. 早期消息淹没当前任务重点；
  2. 工具返回（可能是整篇教案）体积巨大，很快撑爆上下文窗口；
  3. 用户长期偏好（教几年级、什么学科）每次都要重复说明。

本模块把上下文切成 6 层，每层独立管理、独立裁剪：

  L0 identity    身份与系统约束        —— 恒定，永不裁剪
  L1 memory      用户长期记忆          —— 跨会话，结构化摘要
  L2 task        当前任务状态与计划    —— 本次任务的"工作台"
  L3 knowledge   知识库检索结果        —— 按需注入，带来源
  L4 tools       工具调用返回          —— 体积最大，优先裁剪为摘要
  L5 dialogue    近期对话              —— 滑动窗口

装配时按预算从 L5 向上裁剪，保证"永远先丢最不重要的"。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..core.logging_setup import get_logger

log = get_logger("agent.context")

# 中文按 1 token ≈ 1.5 汉字 粗估；宁可高估也不要撑爆窗口
_CHARS_PER_TOKEN = 1.6


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return int(len(text) / _CHARS_PER_TOKEN) + 1


@dataclass
class ToolCallRecord:
    """一次工具调用的痕迹，用于上下文裁剪与结果复用。"""
    tool: str
    args: Dict[str, Any]
    ok: bool
    summary: str                 # 裁剪后保留的摘要
    full: str = ""               # 原始输出（可能被裁剪掉）
    tokens: int = 0
    ts: float = field(default_factory=time.time)


@dataclass
class AgentContext:
    """一次 Agent 运行的完整上下文。"""

    session_id: str = ""
    user_id: str = ""
    goal: str = ""                                    # 用户原始目标
    # L1 长期记忆（学科、年级、风格偏好等）
    memory: Dict[str, Any] = field(default_factory=dict)
    # L2 任务状态
    plan: List[Dict[str, Any]] = field(default_factory=list)
    current_step: int = 0
    task_state: Dict[str, Any] = field(default_factory=dict)
    # L3 检索到的知识
    knowledge: List[Dict[str, Any]] = field(default_factory=list)
    # L4 工具调用历史
    tool_calls: List[ToolCallRecord] = field(default_factory=list)
    # L5 对话
    dialogue: List[Dict[str, str]] = field(default_factory=list)

    def add_message(self, role: str, content: str) -> None:
        self.dialogue.append({"role": role, "content": content, "ts": time.time()})

    def add_knowledge(self, items: List[Dict[str, Any]]) -> None:
        self.knowledge.extend(items)

    def add_tool_call(self, rec: ToolCallRecord) -> None:
        self.tool_calls.append(rec)

    def remember(self, key: str, value: Any) -> None:
        """写入长期记忆（如 subject=初中物理、grade=八年级）。"""
        self.memory[key] = value

    def tool_used(self, name: str) -> bool:
        return any(r.tool == name for r in self.tool_calls)

    def failed_tools(self) -> List[str]:
        return [r.tool for r in self.tool_calls if not r.ok]


class ContextBuilder:
    """按 token 预算装配上下文。"""

    def __init__(self, max_tokens: int = 6000) -> None:
        self.max_tokens = max_tokens

    def build(
        self,
        ctx: AgentContext,
        *,
        system_prompt: str,
        include_knowledge: bool = True,
        include_tools: bool = True,
        max_dialogue_turns: int = 8,
    ) -> List[Dict[str, str]]:
        """返回可直接喂给大模型的 messages 列表。"""
        messages: List[Dict[str, str]] = []

        # L0 身份：恒定
        budget = self.max_tokens - estimate_tokens(system_prompt)
        messages.append({"role": "system", "content": system_prompt})

        # L1 长期记忆：体积小、价值高，优先保留
        if ctx.memory:
            mem_lines = [f"- {k}: {v}" for k, v in ctx.memory.items() if v]
            if mem_lines:
                blob = "[用户长期偏好]\n" + "\n".join(mem_lines)
                t = estimate_tokens(blob)
                if t <= budget:
                    budget -= t
                    messages.append({"role": "system", "content": blob})

        # L2 任务状态与计划
        if ctx.plan:
            lines = []
            for i, step in enumerate(ctx.plan, 1):
                mark = "✓" if step.get("done") else ("→" if i - 1 == ctx.current_step else " ")
                lines.append(f"{mark} {i}. {step.get('description', '')}")
            blob = "[当前任务计划]\n目标：" + ctx.goal + "\n" + "\n".join(lines)
            t = estimate_tokens(blob)
            if t <= budget:
                budget -= t
                messages.append({"role": "system", "content": blob})

        # L3 知识库检索结果（带来源，便于模型做引用）
        if include_knowledge and ctx.knowledge:
            parts = []
            for i, k in enumerate(ctx.knowledge[:8], 1):
                src = k.get("source") or "未知来源"
                content = str(k.get("content", ""))[:800]
                parts.append(f"[{i}] 来源：{src}\n{content}")
            blob = "[参考资料]\n" + "\n\n".join(parts)
            t = estimate_tokens(blob)
            if t <= budget:
                budget -= t
                messages.append({"role": "system", "content": blob})
            else:
                log.info("知识片段超预算，已省略（%d tokens > 剩余 %d）", t, budget)

        # L4 工具调用结果：只放摘要，且从最近的开始放
        if include_tools and ctx.tool_calls:
            parts = []
            for rec in reversed(ctx.tool_calls[-6:]):
                tag = "成功" if rec.ok else "失败"
                parts.append(f"- {rec.tool}({tag})：{rec.summary}")
            blob = "[已完成的操作]\n" + "\n".join(parts)
            t = estimate_tokens(blob)
            if t <= budget:
                budget -= t
                messages.append({"role": "system", "content": blob})

        # L5 对话：滑动窗口，只保留最近 N 轮
        recent = ctx.dialogue[-(max_dialogue_turns * 2):]
        trimmed: List[Dict[str, str]] = []
        used = 0
        for m in reversed(recent):
            t = estimate_tokens(m.get("content", ""))
            if used + t > budget:
                log.info("对话历史触达预算上限，已丢弃更早的 %d 条消息", len(recent) - len(trimmed))
                break
            used += t
            trimmed.append({"role": m["role"], "content": m["content"]})
        messages.extend(reversed(trimmed))

        return messages


def summarize_tool_output(tool: str, result: Any, max_chars: int = 300) -> str:
    """把工具输出压成短摘要，避免把整篇教案塞回上下文。"""
    if isinstance(result, str):
        text = result
    else:
        try:
            import json
            text = json.dumps(result, ensure_ascii=False)
        except Exception:
            text = str(result)
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f" …（已截断，原文 {len(text)} 字）"
