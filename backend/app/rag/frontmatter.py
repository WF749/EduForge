"""极简 YAML frontmatter 解析（知识库文档头部的结构化元数据）。

为什么不用 pyyaml
-----------------
项目红线 8：能复用现有能力就不加依赖。知识库只需要三种写法 ——
`key: value`、内联数组 `key: [a, b]`、块数组（`key:` 后接 `- item`）。
写这 80 行比引入一个依赖更可控，也不会带来版本与安全面。

行为约定（逐条有测试）
----------------------
* 只有**文件开头**以 `---` 独占一行起始、并以 `---` 或 `...` 结束的一段才算
  frontmatter。正文中间的水平分隔线不受影响。
* **解析失败绝不抛异常**：整篇按正文处理。知识库不该因为某个冒号就整篇不入库 ——
  那样教师改了半天发现查不到，而日志里只有一行 YAML 报错。
* 值只做轻量清洗（去引号、去行尾注释），不猜测类型：数字一律保持字符串，
  避免 `grade: 8` 与 `grade: "八年级"` 在过滤时一个匹配得上一个匹配不上。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# 起始必须是文件第一行就是 `---`（允许前面有空行与 BOM）
_START = re.compile(r"^\uFEFF?\s*---\s*$")
_END = re.compile(r"^\s*(?:---|\.\.\.)\s*$")
_KV = re.compile(r"^([A-Za-z0-9_\u4e00-\u9fff\-]+)\s*:\s*(.*)$")

# 知识库约定的元数据键。未知键也保留（不丢信息），但这几个是检索过滤要用的。
KNOWN_KEYS = (
    "stage",      # 学段：小学 / 初中 / 高中 / 通用
    "grades",     # 年级：["七年级"] 或 ["八年级","九年级"]
    "subject",    # 学科：语文 / 数学 / 物理 … 或 通用
    "textbook",   # 教材版本：人教版 / 通用
    "chapter",    # 章节
    "type",       # 内容类型：教学法 / 学科知识点 / 课例 / 活动 / 实验 / 作业 / 评价量规 / 产物模板
)

__all__ = ["split_frontmatter", "parse_frontmatter", "KNOWN_KEYS"]


def _clean_scalar(value: str) -> str:
    v = (value or "").strip()
    # 行尾注释（前面有空格的 #）
    v = re.sub(r"\s+#.*$", "", v).strip()
    # 去掉成对引号
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1].strip()
    return v


def _as_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    text = str(value or "").strip()
    if not text:
        return []
    # 内联数组 [a, b]
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1]
        return [p.strip().strip("\"'") for p in inner.split(",") if p.strip()]
    # 单个标量也按一项处理，方便过滤时用 == 比较
    return [text]


def parse_frontmatter(text: str) -> Dict[str, Any]:
    """只解析 frontmatter 部分，返回字典（不含正文）。失败返回空字典。"""
    meta, _ = split_frontmatter(text)
    return meta


def split_frontmatter(text: str) -> Tuple[Dict[str, Any], str]:
    """把文档拆成 (metadata, 正文)。

    正文**不含** frontmatter —— 这点很关键：否则 `stage: 初中` 这类行会被切进
    chunk，既污染检索，也会在溯源时显示成莫名其妙的正文。
    """
    raw = text or ""
    if not raw:
        return {}, ""

    lines = raw.splitlines()
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i >= len(lines) or not _START.match(lines[i]):
        return {}, raw

    block: List[str] = []
    j = i + 1
    closed = False
    while j < len(lines):
        if _END.match(lines[j]):
            closed = True
            break
        block.append(lines[j])
        j += 1

    if not closed:
        # 开了头却没闭合 —— 按"整篇都是正文"处理，不做半截解析
        return {}, raw

    # 只剥掉前导空行（不剥空格）：否则正文以空行开头，分块时多出一条空 chunk，
    # 标题路径也会因为是第一行而丢失
    body = "\n".join(lines[j + 1:]).lstrip("\n")
    meta: Dict[str, Any] = {}
    pending_list_key: Optional[str] = None

    for line in block:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = _KV.match(line)
        if m:
            key = m.group(1).strip()
            value = _clean_scalar(m.group(2))
            if value == "":
                # `key:` 后面可能跟块数组，先记着
                pending_list_key = key
                meta.setdefault(key, [])
                continue
            pending_list_key = None
            if value.startswith("[") and value.endswith("]"):
                meta[key] = _as_list(value)
            else:
                meta[key] = value
            continue
        # 块数组项：`- 值`
        stripped = line.strip()
        if stripped.startswith("- ") or stripped == "-":
            item = _clean_scalar(stripped[1:])
            if pending_list_key is None:
                pending_list_key = "items"
                meta.setdefault(pending_list_key, [])
            if item:
                meta[pending_list_key].append(item)
            continue
        # 其它写法忽略（不抛错，也不丢正文）

    # 空数组回退成空列表，方便调用方统一处理
    for key in list(meta):
        if meta[key] == []:
            meta[key] = []
    return meta, body


def as_filterable(meta: Dict[str, Any]) -> Dict[str, Any]:
    """整理成可直接用于检索过滤的形态：grades 归一成列表，其余保留标量。"""
    out: Dict[str, Any] = {}
    for key, value in (meta or {}).items():
        if key == "grades":
            out[key] = _as_list(value)
        else:
            out[key] = value
    return out
