"""规则闸门之后的**可选**模型复查（默认关闭、手动触发、只报告）。

与 teaching_compliance（R1–R8 规则）的分工：
  规则查"有没有、合不合规范"——行为动词可不可测量、学段对不对、有没有隐私泄露，
  这些是**确定性**的，离线跑、零额度、每次生成都跑。
  模型查"好不好、能不能真的落地"——45 分钟做不完、某个目标没有对应活动、
  检测覆盖不到目标、学生容易卡住但教案没处理、科学性错误。
  这类问题规则写不出来，只能靠模型，但它慢、要花钱、还会抖，
  所以默认关闭，由教师主动点一次。

三条硬约束：
  1. **默认关闭**（`EDUFORGE_REVIEWER=1` 才开）。擅自开会在每次生成时多一次模型调用，
     既费额度又拖慢生成，而多数教师并不需要。
  2. **只报告**。不改写内容、不让生成失败、不影响合规闸门的结果。
  3. **必须走 llm_service**，绝不自己直连 provider —— 出校插桩在 services/llm 里，
     绕过它就等于让教案正文（可能含学生信息）裸奔出校。scripts/smoke_safety.py
     有一条静态校验盯着本文件不许 import provider。

模型返回的字段名不是枚举（教训见 dialogueFields.js）：
  findings 里每条的键可能任意，所以一律按"缺什么补什么、查不到原样保留"处理，
  绝不因为解析不出来就丢掉整份复查。
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

# 允许的严重程度，模型给别的就降级为 info，不猜
_SEVERITIES = ("high", "medium", "low", "info")

_DIMENSIONS = [
    "课时可行性",      # 45 分钟做不完是最常见的问题
    "目标-活动对应",    # 每个目标有没有活动支撑
    "教学评一致性",     # 检测能不能验证目标达成
    "学生难点预判",     # 哪里会卡住、教案有没有处理
    "科学性",          # 概念/表述有没有错
]

_PROMPT = """你是一位有二十年经验的学科教研员，正在给一份教案做**深度复查**。

前面已经有一套规则检查跑过了（它只查"有没有、合不合规范"：行为动词可测量、学段适配、隐私泄露、课时配平等），
**那些不用你管**。你要看的是规则查不出来的、真正影响这节课上不上的下去的问题：

{dimensions}

【教案内容】
{text}

{meta}

【输出要求】
只输出一个 JSON 对象，不要任何解释文字，不要代码块围栏：
{{
  "summary": "一句话总体评价（80 字以内，先说最要紧的那个问题）",
  "findings": [
    {{"dimension": "上面五个维度之一", "severity": "high|medium|low", "quote": "教案里的原话（没有就空字符串）", "advice": "具体怎么改，能直接照着做"}}
  ]
}}

规则：
- 只报**真的有问题**的，没问题就给空 findings，不要凑数。
- 每条 advice 必须能直接照着改，不要写"建议进一步优化"这种废话。
- 最多 5 条，按严重程度排序。
"""


def review_enabled() -> bool:
    """复查开关。默认关——它慢、要花钱、还会抖，不该自动跑。"""
    return os.getenv("EDUFORGE_REVIEWER", "0").strip().lower() in {"1", "true", "on", "yes"}


def _extract_json(raw: str) -> Optional[Dict[str, Any]]:
    """从模型输出里抠出 JSON。模型爱加围栏、爱在前后说废话，都要能忍。"""
    if not raw:
        return None
    text = raw.strip()
    # 去掉 ```json ... ``` 围栏
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    candidates = [text]
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        candidates.append(m.group())

    for c in candidates:
        try:
            obj = json.loads(c)
            if isinstance(obj, dict):
                return obj
        except Exception:  # noqa: BLE001
            continue
    return None


def _normalize_finding(item: Any) -> Optional[Dict[str, str]]:
    """把一条 finding 规整成固定形状。字段名自由的，缺了补空、多了原样留着。"""
    if isinstance(item, str):
        if not item.strip():
            return None
        return {"dimension": "", "severity": "info", "quote": "", "advice": item.strip()}

    if not isinstance(item, dict):
        return None

    def pick(*keys: str) -> str:
        for k in keys:
            v = item.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return ""

    advice = pick("advice", "suggestion", "建议", "改法", "how")
    quote = pick("quote", "原文", "evidence", "引用")
    # 一句话都没有的条目对教师没用，丢掉
    if not advice and not quote:
        return None

    severity = pick("severity", "level", "严重程度").lower()
    if severity not in _SEVERITIES:
        severity = "info"

    return {
        "dimension": pick("dimension", "维度", "aspect", "type"),
        "severity": severity,
        "quote": quote,
        "advice": advice,
    }


def review_text(
    text: str,
    *,
    meta: Optional[Dict[str, Any]] = None,
    provider: Optional[str] = None,
) -> Dict[str, Any]:
    """对一段教案正文做模型复查。**只报告，不改写。**

    @returns {"enabled","model","summary","findings","raw","reason"}
    """
    if not review_enabled():
        return {
            "enabled": False,
            "reason": "深度复查未开启（设 EDUFORGE_REVIEWER=1 开启）",
            "model": "",
            "summary": "",
            "findings": [],
        }

    body = (text or "").strip()
    if not body:
        return {
            "enabled": False,
            "reason": "没有可复查的内容",
            "model": "",
            "summary": "",
            "findings": [],
        }

    meta = meta or {}
    meta_line = ""
    if meta.get("level") or meta.get("topic") or meta.get("duration"):
        meta_line = "【课程信息】" + " / ".join(
            str(meta[k]) for k in ("level", "topic", "duration") if meta.get(k)
        )

    prompt = _PROMPT.format(
        dimensions="\n".join(f"{i}. {d}" for i, d in enumerate(_DIMENSIONS, 1)),
        text=body[:8000],
        meta=meta_line,
    )

    try:
        # 必须走 llm_service：出校插桩在它里面，绕过去就是裸奔
        from .llm_service import llm_service

        raw = llm_service.chat(prompt, provider=provider) or ""
    except Exception as e:  # noqa: BLE001 —— 复查失败绝不能影响主流程
        return {
            "enabled": False,
            "reason": f"复查调用失败：{type(e).__name__}",
            "model": "",
            "summary": "",
            "findings": [],
        }

    data = _extract_json(raw)
    if data is None:
        # 解析不出来也别丢：把原文交给教师自己看，比一句"复查失败"有用
        return {
            "enabled": True,
            "model": "",
            "summary": (raw or "").strip()[:300],
            "findings": [],
            "raw": True,
            "reason": "模型没有返回结构化结果，已原样附上",
        }

    raw_findings = data.get("findings")
    findings: List[Dict[str, str]] = []
    if isinstance(raw_findings, list):
        for item in raw_findings:
            norm = _normalize_finding(item)
            if norm:
                findings.append(norm)
    elif isinstance(raw_findings, dict):
        norm = _normalize_finding(raw_findings)
        if norm:
            findings.append(norm)

    summary = data.get("summary")
    summary = summary.strip() if isinstance(summary, str) else ""

    return {
        "enabled": True,
        "model": str(data.get("model") or ""),
        "summary": summary,
        "findings": findings[:5],
        "raw": False,
    }
