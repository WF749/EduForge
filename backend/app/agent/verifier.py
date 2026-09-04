"""Verifier —— 结果验证。

验证不是"感觉还行"，而是给出**可判定、可定位**的结论：
  1. 规则校验（零成本）：结构性检查，如教案是否包含必要板块、长度是否合理、
     是否残留占位符/失败标记。
  2. 模型校验（按需）：按评分维度打分，指出具体缺陷位置与修改建议。
  3. 定向修改：把"哪里不行、为什么、怎么改"回传给生成环节重做，
     而不是整篇重生成（省时省额度）。

只有规则校验通过后才调用模型校验，避免无谓开销。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..core.logging_setup import get_logger

log = get_logger("agent.verifier")

# 常见"生成失败"的残留痕迹 —— 出现即判定不合格
_FAILURE_MARKERS = [
    "演示模式", "未调用真实模型", "api key", "api_key", "调用失败",
    "internal server error", "traceback", "none", "null",
]

# 教案/课件的必要板块（命中数量用于结构评分）
_REQUIRED_SECTIONS = {
    "lesson_plan": ["教学目标", "重难点", "教学过程", "板书"],
    "exercise": ["参考答案", "解析"],
}


@dataclass
class VerificationResult:
    passed: bool
    score: float = 0.0                       # 0-1
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    checks: Dict[str, bool] = field(default_factory=dict)
    degraded: bool = False                   # 校验本身未能完成时标记

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed, "score": round(self.score, 3),
            "issues": self.issues, "suggestions": self.suggestions,
            "checks": self.checks, "degraded": self.degraded,
        }


class Verifier:
    """结果验证器。"""

    def __init__(self, min_score: float = 0.6, enable_llm_check: bool = True):
        self.min_score = min_score
        self.enable_llm_check = enable_llm_check

    # ------------------------------------------------------------------

    def verify(
        self,
        goal: str,
        output: str,
        *,
        content_type: str = "general",
        grade: str = "",
        subject: str = "",
    ) -> VerificationResult:
        """先规则、后模型；规则不通过则直接判负，不再花额度调模型。"""
        if not output or not str(output).strip():
            return VerificationResult(False, 0.0, issues=["生成结果为空"])

        issues: List[str] = []
        checks: Dict[str, bool] = {}

        # 1) 失败残留检查
        has_failure_marker = self._check_failure_markers(output)
        checks["无失败残留"] = not has_failure_marker
        if has_failure_marker:
            issues.append("输出中包含调用失败/演示模式的残留痕迹，说明内容未经真实模型生成")

        # 2) 长度合理性
        length_ok = len(str(output).strip()) >= 120
        checks["长度合理"] = length_ok
        if not length_ok:
            issues.append(f"内容过短（{len(str(output).strip())} 字），可能未完整生成")

        # 3) 结构完整性
        required = _REQUIRED_SECTIONS.get(content_type, [])
        if required:
            missing = [s for s in required if s not in output]
            checks["结构完整"] = not missing
            if missing:
                issues.append("缺少必要板块：" + "、".join(missing))

        # 4) 占位符检查
        placeholder = bool(re.search(r"(TODO|待补充|略\{|\{\{|XXX)", output, re.I))
        checks["无占位符"] = not placeholder
        if placeholder:
            issues.append("存在未填充的占位符")

        # 规则分：全部通过为 1.0，逐项扣减
        rule_score = sum(1 for v in checks.values() if v) / max(1, len(checks))
        if rule_score < 1.0:
            return VerificationResult(
                passed=False, score=rule_score * 0.6,
                issues=issues, checks=checks,
                suggestions=["请根据上述问题重新生成，重点补齐缺失板块"],
            )

        # 5) 模型校验（规则已全过才值得花这个钱）
        if not self.enable_llm_check:
            return VerificationResult(True, 1.0, checks=checks, degraded=True)

        return self._llm_verify(goal, output, content_type, grade, subject, checks)

    # ------------------------------------------------------------------

    def _check_failure_markers(self, text: str) -> bool:
        low = text.lower()
        # 只在开头 200 字内检查，避免正文里正常出现的 "None" 被误判
        head = low[:200]
        return any(m.lower() in head for m in _FAILURE_MARKERS if m.lower() != "none")

    def _llm_verify(
        self, goal: str, output: str, content_type: str,
        grade: str, subject: str, checks: Dict[str, bool],
    ) -> VerificationResult:
        from ..core.llm_gateway import llm_chat_json

        prompt = (
            "你是教学内容的质检员。请评估下面这份内容是否达成了用户目标。\n\n"
            f"用户目标：{goal}\n"
            f"学科：{subject or '未指定'}；年级：{grade or '未指定'}；类型：{content_type}\n\n"
            f"待评估内容（节选）：\n{str(output)[:3000]}\n\n"
            "请输出严格 JSON：\n"
            '{"score": 0到1之间的小数, "passed": true或false, '
            '"issues": ["具体缺陷1", "缺陷2"], "suggestions": ["修改建议1"]}\n'
            "评分维度：目标达成度、学科准确性、学段适配性、可操作性。\n"
            "只输出 JSON，不要解释。"
        )
        try:
            data = llm_chat_json(prompt, purpose="verifier", temperature=0.0, max_tokens=600)
            score = float(data.get("score", 0.7))
            passed = bool(data.get("passed", score >= self.min_score))
            issues = [str(x) for x in (data.get("issues") or [])][:5]
            suggestions = [str(x) for x in (data.get("suggestions") or [])][:5]
            if not passed and not issues:
                issues.append(f"模型评分 {score:.2f} 低于阈值 {self.min_score}")
            return VerificationResult(passed, score, issues, suggestions, checks)
        except Exception as e:
            log.warning("模型校验失败，以规则结果为准: %s", e)
            # 校验本身失败不能假装通过 —— 标记为 degraded 让上层知情
            return VerificationResult(True, 1.0, checks=checks, degraded=True,
                                      issues=[f"自动校验未能完成：{e}"])

    # ------------------------------------------------------------------

    def build_revision_prompt(self, original_goal: str, output: str, v: VerificationResult) -> str:
        """把验证结论转成**定向修改**指令，避免整篇重生成。"""
        parts = [
            "上一版内容存在以下问题，请在**保留已有正确部分**的基础上做定向修改：\n",
        ]
        if v.issues:
            parts.append("问题：\n" + "\n".join(f"- {x}" for x in v.issues))
        if v.suggestions:
            parts.append("\n修改要求：\n" + "\n".join(f"- {x}" for x in v.suggestions))
        parts.append(f"\n原始需求：{original_goal}\n")
        parts.append("上一版内容：\n" + str(output)[:6000])
        parts.append("\n请输出修改后的完整内容。")
        return "\n".join(parts)
