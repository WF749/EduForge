"""任意形状 → 可读文本：写进成品（Word / PPT）前的**最后一道闸门**。

为什么要有这个模块
------------------
模型返回的字段形状不固定：`str` / `dict` / `list` / 嵌套，甚至是**长得像 Python
字面量的字符串**（提示词里给的是 Python 风格示例，模型就把 repr 照抄回来）。

渲染代码里只要有一处写了 `str(v)`，就会把语言内部的表示法印进成品：

    Word 单元格里躺着  {'具体目标': "能准确说出…"}
    PPT 要点里躺着    ['控制变量法验证：①…；②…']

这不是排版瑕疵 —— 教师打开文件的第一眼看到的是**程序内部的数据结构**，
整个产物的可信度就此归零。这两形态本项目都真实产出过。

设计原则
--------
1. **表示法绝不外泄**：dict / list 一律摊成「键：值」与项目符号，不输出 `{}`、`[]`、引号。
2. **判定不了也要降级，不能原样保留**：`ast.literal_eval` 会因为截断、值里含引号
   或特殊符号而失败。此时宁可格式朴素（尽力读出键值），也不能留下 repr。
3. **绝不丢内容**：降级再难看，也要把文字留下来。丢内容比格式丑严重得多。
4. **纯标准库**：只依赖 `re` / `ast`。

所有进入 docx / pptx 的文本都应当经过 `safe_text()`。
"""

from __future__ import annotations

import ast
import re
from typing import Any, Dict, List, Tuple

# 「- xxx」「1. xxx」「• xxx」这类行首标记，判断字面量前要先剥掉
# 允许**多重**行首标记：模型与上游渲染都可能已经加过一轮 `• `，
# 再叠加一层就变成 `• • ['…']` —— 只剥一层的话后面的 repr 就判不出来。
_LIST_MARKER = re.compile(r"^(?:\s*(?:[-*•◦▪]|\d+[.、])\s*)+")

# `'键': '值'` / `"键": "值"` —— 用于 literal_eval 失败后的尽力降级
_LITERAL_PAIR = re.compile(
    r"""\s*['"]?(?P<key>[^'"{}[\]:,]{1,40})['"]?\s*[:：]\s*(?P<val>.*?)\s*$""",
    re.S,
)

_MAX_DEPTH = 6


def plain_scalar(value: Any) -> str:
    """标量 → 文本。空值给空串，布尔给人话，整数不做 float 化。"""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, (int, float, str)):
        return str(value).strip()
    return ""


def _split_top_level(text: str) -> List[str]:
    """按顶层逗号切分，跳过引号内部与嵌套括号。

    为什么要自己写而不直接 split：值里经常带逗号（「①单位换算正确；②…」），
    直接切会把一条内容劈成两半，反而更看不懂。
    """
    parts: List[str] = []
    buf: List[str] = []
    quote: str = ""
    depth = 0
    for ch in text:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in ("'", '"'):
            quote = ch
            buf.append(ch)
            continue
        if ch in "{[(":
            depth += 1
        elif ch in "}])":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    if buf:
        parts.append("".join(buf))
    return [p for p in (x.strip() for x in parts) if p]


def degrade_literal(body: str) -> str:
    """literal_eval 失败时的兜底：把 `{'k': 'v', …}` 尽力读成人话。

    为什么不能"判定不了就原样保留"：解析失败恰恰是**最常见**的情况 ——
    模型输出的 repr 经常因为截断、值里含引号或全角符号而无法 literal_eval。
    这时若原样返回，用户看到的就是 Word 里躺着 `{'具体目标': "能准确说出…`。
    """
    inner = body.strip()
    # 括号**各端独立**剥离：模型输出的 repr 经常在末尾被截断
    # （`{'具体目标': '能说出…` 没有右花括号），要求首尾成对就等于放弃处理。
    if inner[:1] in "{[":
        inner = inner[1:].strip()
    if inner[-1:] in "}]":
        inner = inner[:-1].strip()
    if not inner:
        return ""

    chunks = _split_top_level(inner)
    out: List[str] = []
    for chunk in chunks:
        m = _LITERAL_PAIR.match(chunk)
        if m:
            key = m.group("key").strip().strip("'\"").strip()
            val = m.group("val").strip()
            # 值可能还套着一层引号；截断时会只剩开头的半个引号，也要剥掉
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
                val = val[1:-1]
            else:
                val = val.lstrip("'\"")
            val = val.strip()
            out.append(f"{key}：{val}" if val else key)
        else:
            cleaned = chunk.strip()
            if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in "'\"":
                cleaned = cleaned[1:-1].strip()
            if cleaned:
                out.append(cleaned)
    return "；".join(out) if out else ""


def heal_literals(value: Any, depth: int = 0) -> Any:
    """把"长得像 Python 字面量"的字符串还原成结构；还原不了就降级成人话。"""
    if depth > _MAX_DEPTH:
        return value
    if isinstance(value, dict):
        return {k: heal_literals(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [heal_literals(v, depth + 1) for v in value]
    if not isinstance(value, str):
        return value

    body = _LIST_MARKER.sub("", value).strip()
    if len(body) < 4 or len(body) > 20000:
        return value
    if not ((body.startswith("{") and body.endswith("}"))
            or (body.startswith("[") and body.endswith("]"))):
        return value

    try:
        parsed = ast.literal_eval(body)
    except (ValueError, SyntaxError, MemoryError, RecursionError):
        # 关键：解析失败**不能**原样返回，那等于把 repr 送进成品
        degraded = degrade_literal(body)
        return degraded or value

    if isinstance(parsed, (dict, list)):
        return heal_literals(parsed, depth + 1)
    return value


def heal_lines(value: Any) -> Any:
    """多行文本**逐行**自愈。

    为什么不能只整串判定：模型常把要点写成多行，
    其中只有某一行是 repr —— 整串以「• 公式含义…」开头，既不以 `{` 也不以 `[`
    开头，整串判定直接放弃，那一行 repr 就漏进了成品（线上真实出现过：
    PPT 第 6 页要点里躺着 `['控制变量法验证：①…']`）。
    逐行判定就能各自处理。
    """
    healed = heal_literals(value)
    if isinstance(healed, str) and "\n" in healed:
        parts = []
        for line in healed.split("\n"):
            one = heal_literals(line)
            # 单行可能被还原成 dict/list —— 拼回文本前先摊平，否则 join 会炸
            parts.append(one if isinstance(one, str) else plain_block(one))
        return "\n".join(parts)
    return healed


def flatten(value: Any, level: int = 0) -> List[Tuple[int, str]]:
    """任意形状 → [(层级, 文本)]。

    dict → 「键：值」，值还是复合结构就下沉一层；
    list → 逐项摊平（**不**输出方括号与引号）；
    标量 → 原样。
    """
    rows: List[Tuple[int, str]] = []
    if isinstance(value, dict):
        for key, sub in value.items():
            name = plain_scalar(key) or str(key).strip()
            if isinstance(sub, (dict, list, tuple)):
                kids = flatten(sub, level + 1)
                if len(kids) == 1 and kids[0][0] == level + 1:
                    rows.append((level, f"{name}：{kids[0][1]}"))
                elif kids:
                    rows.append((level, f"{name}："))
                    rows.extend(kids)
                else:
                    rows.append((level, name))
            else:
                text = plain_scalar(sub)
                rows.append((level, f"{name}：{text}" if text else name))
    elif isinstance(value, (list, tuple)):
        for sub in value:
            rows.extend(flatten(sub, level))
    else:
        text = plain_scalar(value)
        if text:
            rows.append((level, text))
    return rows


def plain_block(value: Any, max_rows: int = 60) -> str:
    """摊成多行文本（写进表格单元格）。

    层级用缩进 + 项目符号表达 —— **不用** `- ` 这种伪列表：
    那在 Word 里就是个普通破折号，既没有悬挂缩进也不会随样式变。
    """
    rows = flatten(heal_lines(value))[:max_rows]
    if not rows:
        return ""
    lines = []
    for lv, text in rows:
        lines.append(text if lv == 0 else f"{'    ' * (lv - 1)}• {text}")
    return "\n".join(lines)


def numbered_block(value: Any, max_rows: int = 60) -> str:
    """像 plain_block，但顶层条目带序号（教学目标这类"几条"的内容）"""
    rows = flatten(heal_lines(value))[:max_rows]
    if not rows:
        return ""
    lines: List[str] = []
    n = 0
    for lv, text in rows:
        if lv == 0:
            n += 1
            lines.append(f"{n}. {text}")
        else:
            lines.append(f"{'    ' * (lv - 1)}• {text}")
    return "\n".join(lines)


# 成品里一旦出现这些，就说明有数据结构泄漏了 —— 测试用它们兜底
REPR_MARKS = ("{'", "{'", '["', "['", "{u'", '{"')


def safe_text(value: Any, *, numbered: bool = False, max_rows: int = 60) -> str:
    """**出口闸门**：任何形状 → 保证不含 repr 的可读文本。

    写入 docx / pptx 前统一过这一道。即使上游某条渲染路径忘了调用清洗，
    这里也不会把 `{'…'}` / `[…]` 放进成品。
    """
    healed = heal_lines(value)
    text = numbered_block(healed, max_rows) if numbered else plain_block(healed, max_rows)
    # 兜底中的兜底：万一还有残留，降级一次，绝不原样吐出去
    if any(m in text for m in REPR_MARKS):
        text = degrade_literal(text) or text
    return text


def looks_like_repr(text: str) -> bool:
    """文本里是否还残留 Python 表示法。供回归测试断言。"""
    return any(m in text for m in REPR_MARKS)
