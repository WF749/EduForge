"""按契约生成"能上课"的课件：LLM 产出 → 校验 → 不合格就定向重做。

为什么不是"生成一次就完事"
--------------------------
模型第一次输出几乎总会缺点什么（少一段闭环、练习忘了给答案、某页留了占位符）。
本模块把 `validate_deck` 当成**闸门**：不合格就把**具体问题**塞回 prompt 让模型改，
而不是笼统地说"重做一遍"。

有界自主（不做无限重试）
----------------------
- `max_rounds` 默认 3（含首次），超过就用最后一次结果并**如实标注未通过项**；
- 每轮都把上一轮的错误原文回传，避免原地打转；
- 任何异常都返回 None，由调用方降级（不要让教师等半天最后什么都没有）。

内容来源可追溯
--------------
教材定位（`textbook_index`）会写进 prompt；查不到时明确要求"不要编造章节号"。
生成的每份课件都带 `provenance`：教材依据、生成依据、模型、轮次。
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from . import lesson_deck as LD
from . import textbook_index as TBI


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_SCHEMA_HINT = """输出**严格 JSON**（不要 Markdown 代码块，不要注释），结构如下：

{
  "meta": {"band":"小学|初中|高中","grade":"八年级","subject":"物理",
           "version":"人教版","topic":"浮力","period":"第1课时","subtitle":"10.1 浮力"},
  "slides": [
    {"type":"cover"},
    {"type":"objectives","title":"学习目标","items":[{"tag":"1","text":"会……"},…]},
    {"type":"divider","no":"第一板块","title":"情境导入","subtitle":"……"},
    {"type":"points","title":"情境导入·生活中的现象","items":["…","…"]},
    {"type":"activity","title":"探究实验·……","goal":"……","steps":["…","…"],"tip":"……"},
    {"type":"concept","title":"结论·……","big":"一句话结论","points":["…","…"]},
    {"type":"example","title":"例题·……","problem":"题目","steps":["…","…"],"answer":"完整答案"},
    {"type":"exercise","title":"课堂练习","items":[{"q":"题目","a":"答案"},…]},
    {"type":"table","title":"……","headers":["…"],"rows":[["…"]],"note":"……"},
    {"type":"summary","title":"课堂小结","items":["…","…"]},
    {"type":"homework","title":"布置作业","required":["…"],"optional":["…"],"practice":["…"]},
    {"type":"end","title":"谢谢观看","subtitle":"……"}
  ]
}

每一页还可以带可选字段 "teacher_note": {"say":"讲什么","ask":"问什么","minutes":"几分钟","transition":"过渡语"}。"""


_RULES = """硬性要求（违反即不合格，会被打回重做）：
1. **零占位符**：不得出现"请填写、待补充、TODO、此处插入、示例内容、自行设计、图片来源、XXX、PXX、长串下划线"。
2. **教学闭环六段齐全**：导入、新知、活动、练习、小结、作业，一段都不能少。
3. **练习必须给答案**：每题都要有 "a" 字段（答案 + 简要解析）。
4. **例题要有完整解题步骤和最终答案**（steps + answer）。
5. **活动要可执行**：有 goal（目标）+ steps（步骤）；不能只写"小组讨论"。
6. **每页带 teacher_note**：讲什么(say)/问什么(ask)/几分钟(minutes)/过渡语(transition)。
7. **内容匹配学段**：不超纲、不低幼化；术语、单位、符号正确。
8. 一节课 14–18 页，不要凑页数，每页都要能明确回答"这页在课上干什么"。
9. 教材依据按下面给出的信息写；**若说"本地暂无对应教材"，就不要编造章节号**，按知识点体系组织。"""


def _build_prompt(subject: str, grade: str, topic: str, band: str,
                  period: str, version: str, key_points: str,
                  textbook_hint: str, fewshot: str,
                  errors: Optional[List[str]] = None) -> str:
    head = [
        f"你是资深 K12 {subject}教师，也是课件设计专家。",
        f"请为下面这节课设计一份**可以直接上课**的完整课件：",
        f"  学科：{subject}   年级：{grade or '（未指定，按学段常见安排）'}",
        f"  学段：{band or '初中'}   课题：{topic}   课时：{period or '第1课时'}",
        f"  教材版本：{version or '（未指定，按人教版的常见编排）'}",
    ]
    if key_points:
        head.append(f"  必须覆盖的知识点：{key_points}")
    head.append("")
    head.append(f"【教材依据】{textbook_hint}")
    if fewshot:
        head.append("")
        head.append("【参考范例（结构与颗粒度照此，内容必须原创）】")
        head.append(fewshot[:3500])
    head.append("")
    head.append(_RULES)
    head.append("")
    head.append(_SCHEMA_HINT)
    if errors:
        head.append("")
        head.append("【上一轮被判不合格，必须修正以下问题】")
        for e in errors[:12]:
            head.append(f"- {e}")
        head.append("请只输出修正后的完整 JSON。")
    return "\n".join(head)


# ---------------------------------------------------------------------------
# JSON 解析（模型经常包 ```json 或加前后说明）
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    s = text.strip()
    # 去掉 Markdown 代码块
    m = re.search(r"```(?:json)?\s*(.*?)```", s, re.S)
    if m:
        s = m.group(1).strip()
    # 直接尝试
    try:
        return json.loads(s)
    except Exception:
        pass
    # 截取第一个 { 到最后一个 }
    i, j = s.find("{"), s.rfind("}")
    if i >= 0 and j > i:
        try:
            return json.loads(s[i:j + 1])
        except Exception:
            return None
    return None


# ---------------------------------------------------------------------------
# 生成入口
# ---------------------------------------------------------------------------

def generate(subject: str, topic: str, *, grade: str = "", band: str = "",
             period: str = "", version: str = "", key_points: str = "",
             max_rounds: int = 3,
             caller: Any = None) -> Optional[Dict[str, Any]]:
    """生成一份符合契约的课件。

    @param caller 注入的 LLM 调用函数（测试用）；默认用 llm_client.blocking_chat
    @returns deck（含 provenance）；失败返回 None
    """
    from .. import llm_client

    def _chat(prompt: str) -> str:
        if caller is not None:
            return caller(prompt)
        return llm_client.blocking_chat(
            [{"role": "user", "content": prompt}], max_tokens=6000
        ) or ""

    band = band or ("小学" if "年级" not in (grade or "") else "初中")
    textbook_hint = TBI.describe(subject, grade, topic)
    fewshot = LD.golden_fewshot(subject, limit=1)

    last: Optional[Dict[str, Any]] = None
    last_report: Dict[str, Any] = {}
    rounds_used = 0

    errors: Optional[List[str]] = None
    for r in range(max(1, min(max_rounds, 4))):
        rounds_used = r + 1
        prompt = _build_prompt(subject, grade, topic, band, period, version,
                               key_points, textbook_hint, fewshot, errors)
        try:
            raw = _chat(prompt)
        except Exception:
            break
        deck = _extract_json(raw)
        if not isinstance(deck, dict):
            errors = ["输出不是合法 JSON"]
            continue
        report = LD.validate_deck(deck)
        last_report = report
        # meta 兜底：模型有时把课题信息放在外层
        meta = deck.setdefault("meta", {})
        meta.setdefault("subject", subject)
        meta.setdefault("topic", topic)
        meta.setdefault("grade", grade)
        meta.setdefault("band", band)
        meta.setdefault("period", period or "第1课时")
        meta.setdefault("version", version)
        last = deck
        if report.get("ok"):
            break
        errors = report.get("errors") or ["未通过校验"]

    if last is None:
        return None

    last["provenance"] = {
        "textbook": textbook_hint,
        "has_textbook": TBI.lookup(subject, grade, topic) is not None,
        "generator": "llm",
        "rounds": rounds_used,
        "validated": bool(last_report.get("ok")),
        "scores": last_report.get("scores") or {},
        "total": last_report.get("total"),
        "issues": (last_report.get("errors") or [])[:8],
        "warnings": (last_report.get("warnings") or [])[:4],
    }
    return last


def generate_from_golden(subject: str, topic: str) -> Optional[Dict[str, Any]]:
    """命中内置黄金样例时直接复用（零成本、质量可控），并标注来源。"""
    g = LD.find_golden(subject, topic)
    if not g:
        return None
    deck = json.loads(json.dumps(g, ensure_ascii=False))
    meta = deck.setdefault("meta", {})
    meta.setdefault("subject", g.get("subject"))
    meta.setdefault("topic", g.get("title"))
    meta.setdefault("grade", g.get("grade"))
    meta.setdefault("band", g.get("band"))
    meta.setdefault("version", g.get("version"))
    meta.setdefault("period", g.get("period") or "第1课时")
    deck["provenance"] = {
        "textbook": TBI.describe(subject, g.get("grade") or "", topic),
        "has_textbook": TBI.lookup(subject, g.get("grade") or "", topic) is not None,
        "generator": "golden_deck",
        "rounds": 0,
        "validated": True,
        "scores": LD.validate_deck(deck).get("scores", {}),
    }
    return deck
