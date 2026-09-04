"""输入数据分级（对齐 JY/T 0661-2025 教育数据分类分级）。

级别定义
--------
  L1 公开      可对外公开
  L2 内部      校内一般数据（默认档：普通教学内容、课题、知识点）
  L3 敏感      含个人身份标识，或整段考试试题
  L4 重要      含未成年人敏感个人信息（身份证号、成绩名单、学生名单）
  L5 核心      关系国家安全/重大公共利益（本产品不涉及，保留位）

为什么正则而不是模型
--------------------
用模型识别敏感信息听起来更高级，但这里有个致命问题：
**识别本身就要把原文送进模型**。若那个模型在云端，等于为了防泄漏先泄漏一次。
因此识别必须在本地完成、零网络依赖，正则 + 结构规则是唯一自洽的选择。

代价是精度有限，这一点如实说明：
  - **高置信规则**（身份证/手机号/邮箱/考号）：误报极低，可直接用于阻断
  - **结构规则**（成绩表/试题段/名单）：可能误报，因此默认只告警不阻断

宁可漏报也不误报阻断，是刻意的取舍 —— 阻断会直接打断教师的工作流，
而本模块的目的是"让流向可见"，不是当守门员。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

LEVELS = ("L1", "L2", "L3", "L4", "L5")

# 达到该级别即视为"不应出校"
EGRESS_BLOCK_LEVEL = "L3"


def level_rank(level: str) -> int:
    """把 L1~L5 映射为 1~5，便于比较。未知级别按 L1 处理（不放大风险）。"""
    try:
        return LEVELS.index(level) + 1
    except ValueError:
        return 1


@dataclass
class Finding:
    """一类命中。注意：**不保存原文**，只存脱敏后的样例，避免日志二次泄漏。"""

    kind: str
    label: str
    level: str
    count: int
    sample: str = ""      # 已脱敏

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "label": self.label,
            "level": self.level,
            "count": self.count,
            "sample": self.sample,
        }


@dataclass
class Classification:
    level: str                                  # 整体定级（取所有命中的最高级）
    findings: List[Finding] = field(default_factory=list)

    @property
    def is_sensitive(self) -> bool:
        return level_rank(self.level) >= level_rank(EGRESS_BLOCK_LEVEL)

    def to_dict(self) -> dict:
        return {"level": self.level, "findings": [f.to_dict() for f in self.findings]}


def _mask(s: str, keep_head: int = 0, keep_tail: int = 0) -> str:
    """脱敏样例：只保留首尾若干字符，其余打星。"""
    if len(s) <= keep_head + keep_tail:
        return "*" * len(s)
    return s[:keep_head] + "*" * (len(s) - keep_head - keep_tail) + s[keep_tail:]


def _mask_phone(p: str) -> str:
    return p[:3] + "****" + p[-4:] if len(p) >= 7 else "*" * len(p)


# ---------------------------------------------------------------------------
# 规则
# ---------------------------------------------------------------------------

# 身份证号：18 位，末位为数字或 X。前后不能接数字，避免匹配长数字串的片段。
RE_ID_CARD = re.compile(r"(?<![0-9])\d{17}[0-9Xx](?![0-9])")

# 手机号：1[3-9] 开头 11 位
RE_PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")

RE_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# 学号 / 学籍号 / 考号 / 准考证号：关键词 + 数字串
# 用宽松的间隔（允许空格、冒号、括号）以覆盖 "学号：20230101" 这类写法
RE_STUDENT_ID = re.compile(
    r"(学号|学籍号|考号|准考证号|学籍编号)\s*[:：]?\s*([0-9]{6,20})"
)

# 成绩表：姓名式 token + 疑似分数，且附近有成绩类关键词
# 例："张三 85 李四 92 王五 78"
#
# 末尾的 (?!\s*[%％人]) 是必要的：否则 "掌握率 42%" 会被当成"姓名+分数"
# （正则可以从"掌"字起匹配到"掌握率 42"），把统计指标误判成学生并脱敏成"学生D"。
# 数字后跟 % 或"人"的是比率/人数，不是分数 —— 而"班级 45 人"同样应被排除。
#
# `(?!\d)` 不可省：没有它时引擎会回溯成 "掌握率 4"（\d{1,3} 只吃一位）
# 从而绕开后面的百分比检查，负向前瞻形同虚设。
RE_SCORE_PAIR = re.compile(
    r"([\u4e00-\u9fa5]{2,4})\s*[:：\s]\s*(\d{1,3}(?:\.\d)?)(?!\d)\s*(?:分)?(?!\s*[%％人])"
)
RE_SCORE_CTX = re.compile(r"(成绩|分数|得分|掌握率|正确率|排名|月考|期末|期中)")

# 整段试题：连续编号题干 + 选择题选项
RE_QNUM = re.compile(r"(?m)^\s*\d{1,3}\s*[.、．)]\s*\S")
RE_OPTION = re.compile(r"(?m)^\s*[ABCD]\s*[.、．)]\s*\S")

# 名单：名单类关键词 + 顿号/逗号分隔的多个中文姓名
RE_ROSTER_KW = re.compile(r"(名单|花名册|名册|点名册)")
RE_ROSTER_NAME = re.compile(r"[\u4e00-\u9fa5]{2,4}(?=\s*[、,，])")


def _find(text: str) -> List[Finding]:
    out: List[Finding] = []

    m = RE_ID_CARD.findall(text)
    if m:
        out.append(Finding("id_card", "身份证号", "L4", len(m), _mask(m[0], 3, 2)))

    m = RE_PHONE.findall(text)
    if m:
        out.append(Finding("phone", "手机号", "L3", len(m), _mask_phone(m[0])))

    m = RE_EMAIL.findall(text)
    if m:
        out.append(Finding("email", "电子邮箱", "L3", len(m), _mask(m[0], 2, 0)))

    m = RE_STUDENT_ID.findall(text)
    if m:
        out.append(Finding("student_id", "学号/考号", "L3", len(m),
                           f"{m[0][0]}={_mask(m[0][1], 2, 2)}"))

    # 成绩表：需要 "姓名+分数" 至少 3 组，且文本里有成绩类上下文词
    pairs = RE_SCORE_PAIR.findall(text)
    if len(pairs) >= 3 and RE_SCORE_CTX.search(text):
        out.append(Finding("score_table", "成绩/正确率名单", "L4", len(pairs),
                           f"{pairs[0][0]}=***"))

    # 名单：关键词 + 至少 3 个顿号分隔的中文词
    if RE_ROSTER_KW.search(text):
        names = RE_ROSTER_NAME.findall(text)
        if len(names) >= 3:
            out.append(Finding("roster", "学生名单", "L4", len(names), "***"))

    # 整段试题：题号 >= 4 且出现 ABCD 选项
    qnum = RE_QNUM.findall(text)
    if len(qnum) >= 4 and RE_OPTION.search(text):
        out.append(Finding("exam_paper", "整段考试试题", "L3", len(qnum), "***"))

    return out


def classify(*parts: str) -> Classification:
    """对若干文本片段做整体定级。

    传入多段（system / history / prompt）而不是只传 prompt，
    因为敏感信息可能出现在任何一段 —— 只看 prompt 会漏掉历史消息里的名单。
    """
    text = "\n".join(p for p in parts if p)
    if not text.strip():
        return Classification(level="L1", findings=[])

    findings = _find(text)
    if not findings:
        # 有内容但无命中 → 校内一般教学数据
        return Classification(level="L2", findings=[])

    top = max(findings, key=lambda f: level_rank(f.level))
    return Classification(level=top.level, findings=findings)
