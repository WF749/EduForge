"""脱敏：确需上云时，保留教学语义、抹掉身份标识。

能脱敏的和不能脱敏的（必须说清楚）
--------------------------------
**能**：个人身份标识符 —— 身份证号、手机号、邮箱、学号、成绩单里的姓名。
      抹掉这些不影响教学活动本身：AI 依然知道"班级掌握率 42%"，
      只是不知道"张三 42 分"。而前者才是备课真正需要的信号。

**不能**：整段考试试题。教学价值恰恰就在题面本身，
      抹掉题面等于抹掉全部用途。这类只能靠**本地模型**解决，
      不能假装"脱敏后就可以上云"。

因此 `redact()` 只处理身份标识，遇到试题会原样保留 ——
调用方仍需看 `RouteDecision.action` 决定是否放行。
"""

from __future__ import annotations

import re
from typing import Dict, Tuple

from .classifier import (
    RE_EMAIL,
    RE_ID_CARD,
    RE_PHONE,
    RE_ROSTER_NAME,
    RE_SCORE_PAIR,
    RE_STUDENT_ID,
)

_PSEUDO = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _pseudonym_map(names) -> Dict[str, str]:
    """同一姓名固定映射为同一个代号，保证前后文一致。"""
    mapping: Dict[str, str] = {}
    for n in names:
        if n in mapping:
            continue
        idx = len(mapping)
        mapping[n] = f"学生{_PSEUDO[idx]}" if idx < len(_PSEUDO) else f"学生{idx + 1}"
    return mapping


def redact(text: str) -> Tuple[str, int]:
    """脱敏文本，返回 (脱敏后文本, 替换次数)。

    只处理身份标识；试题内容原样保留（原因见模块 docstring）。
    """
    if not text:
        return text, 0
    total = 0

    def _sub(pattern: re.Pattern, repl) -> None:
        nonlocal text, total
        text, n = pattern.subn(repl, text)
        total += n

    _sub(RE_ID_CARD, "[身份证号已移除]")
    _sub(RE_PHONE, "[手机号已移除]")
    _sub(RE_EMAIL, "[邮箱已移除]")
    # 学号保留字段名，只抹号 —— 让模型仍知道"这是学号"这个语义
    _sub(RE_STUDENT_ID, lambda m: f"{m.group(1)}：{m.group(2)[:2]}****{m.group(2)[-2:]}")

    # 姓名 → 代号：只在确实存在"姓名+分数"配对时替换，
    # 避免误伤正常教学文本（如古诗里的"李白"）
    pairs = RE_SCORE_PAIR.findall(text)
    if len(pairs) >= 3:
        mapping = _pseudonym_map([p[0] for p in pairs])
        # 长名优先，避免 "欧阳" 先被替换导致 "欧阳明日" 残留。
        # 前瞻条件必须与 RE_SCORE_PAIR 完全一致（含数字右边界与百分比排除），
        # 否则 "掌握率 42%" 会被这里单独命中，替换成"学生D 42%"。
        for name in sorted(mapping, key=len, reverse=True):
            text, n = re.subn(
                re.escape(name)
                + r"(?=\s*[:：\s]\s*\d{1,3}(?:\.\d)?(?!\d)\s*(?:分)?(?!\s*[%％人]))",
                mapping[name], text,
            )
            total += n
    else:
        roster = RE_ROSTER_NAME.findall(text)
        if len(roster) >= 3:
            mapping = _pseudonym_map(roster)
            for name in sorted(mapping, key=len, reverse=True):
                text, n = re.subn(re.escape(name), mapping[name], text)
                total += n

    return text, total
