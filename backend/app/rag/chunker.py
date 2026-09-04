"""中文结构感知分块。

为什么不用固定长度切
--------------------
教学资料是 Markdown，标题本身就是最强的语义边界。
按固定字数硬切会出现两种伤：
  1. 一个知识点被拦腰截断，检索到的片段读不通，模型据此作答会跑偏；
  2. 溯源时只能告诉你"第 3 个片段"，而教师需要的是"《一元二次方程》→ 求根公式"。

因此这里保留**标题路径**，并把标题前置到 chunk 文本里，
让向量化时标题语义也参与编码（对短 chunk 的召回提升明显）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

# Markdown / 中文标题行
_HEADING_RE = re.compile(r"^(#{1,6})\s*(.+?)\s*$")
# 中文句末标点 + 换行
_SENT_SPLIT_RE = re.compile(r"(?<=[。！？；!?;])|\n+")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")

DEFAULT_CHUNK_SIZE = 320      # 中文字符数
DEFAULT_CHUNK_OVERLAP = 60


@dataclass
class Chunk:
    text: str                  # 实际入库文本（含标题前缀）
    raw_text: str              # 去掉标题前缀的原文，用于展示
    heading_path: str          # 例如 "一元二次方程 > 求根公式"
    chunk_index: int           # 文档内序号
    char_start: int
    char_end: int

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "raw_text": self.raw_text,
            "heading_path": self.heading_path,
            "chunk_index": self.chunk_index,
            "char_start": self.char_start,
            "char_end": self.char_end,
        }


def is_chinese(text: str) -> bool:
    """判断文本主体是否为中文（决定分句策略）。"""
    stripped = re.sub(r"\s", "", text or "")
    if not stripped:
        return False
    cjk = sum(1 for c in stripped if _CJK_RE.match(c))
    return cjk / len(stripped) > 0.3


def _split_sentences(text: str) -> List[str]:
    parts = _SENT_SPLIT_RE.split(text or "")
    return [p.strip() for p in parts if p and p.strip()]


def _split_long_sentence(s: str, size: int) -> List[str]:
    """超长句兜底：按标点再切，仍过长则按字数硬切。"""
    if len(s) <= size:
        return [s]
    pieces: List[str] = []
    cur = ""
    for ch in s:
        cur += ch
        if ch in "，,、）)】]" and len(cur) >= size * 0.6:
            pieces.append(cur)
            cur = ""
        elif len(cur) >= size:
            pieces.append(cur)
            cur = ""
    if cur:
        pieces.append(cur)
    return pieces


def _merge_sentences(
    sentences: List[str], size: int, overlap: int, chinese: bool
) -> List[str]:
    """贪心合并句子为不超过 size 的块，块间重叠 overlap 字符。"""
    chunks: List[str] = []
    cur = ""
    for s in sentences:
        for piece in _split_long_sentence(s, size):
            # 中文直接拼接（无空格），英文保留空格
            sep = "" if chinese else " "
            candidate = (cur + sep + piece).strip() if cur else piece
            if len(candidate) <= size:
                cur = candidate
                continue
            if cur:
                chunks.append(cur)
                if overlap > 0 and chinese:
                    cur = (cur[-overlap:] + piece).strip()
                elif overlap > 0:
                    tail_words = cur.split()[-overlap // 5:]
                    cur = (" ".join(tail_words) + " " + piece).strip()
                else:
                    cur = piece
            else:
                cur = piece
    if cur.strip():
        chunks.append(cur.strip())
    return chunks


def split_markdown_sections(content: str) -> List[tuple]:
    """按 Markdown 标题切成 [(heading_path, body_text), ...]。

    标题层级用栈维护，得到完整路径。
    """
    if not content or not content.strip():
        return []

    lines = content.splitlines()
    sections: List[tuple] = []
    stack: List[tuple] = []      # [(level, title)]
    buf: List[str] = []
    cur_path: List[str] = []

    def _flush() -> None:
        body = "\n".join(buf).strip()
        if body:
            sections.append((" > ".join(cur_path), body))
        buf.clear()

    for line in lines:
        m = _HEADING_RE.match(line.strip())
        if m:
            _flush()
            level = len(m.group(1))
            title = m.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            cur_path = [t for _, t in stack]
            continue
        buf.append(line)
    _flush()

    # 没有标题的纯文本：整篇作为一个 section
    if not sections:
        body = content.strip()
        if body:
            sections.append(("", body))
    return sections


def chunk_document(
    content: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    source: str = "",
) -> List[Chunk]:
    """把一篇文档切成带标题路径的 chunk 列表。"""
    if not content or not content.strip():
        return []

    chinese = is_chinese(content)
    chunks: List[Chunk] = []
    cursor = 0

    for heading_path, body in split_markdown_sections(content):
        sentences = _split_sentences(body)
        if not sentences:
            continue
        pieces = _merge_sentences(sentences, chunk_size, chunk_overlap, chinese)
        for piece in pieces:
            raw = piece.strip()
            if not raw:
                continue
            # 标题前置：让标题语义参与向量编码
            text = f"【{heading_path}】\n{raw}" if heading_path else raw
            start = content.find(raw, cursor)
            if start < 0:
                start = cursor
            end = start + len(raw)
            cursor = max(cursor, end)
            chunks.append(
                Chunk(
                    text=text,
                    raw_text=raw,
                    heading_path=heading_path,
                    chunk_index=len(chunks),
                    char_start=start,
                    char_end=end,
                )
            )
    return chunks


def chunk_stats(chunks: List[Chunk]) -> dict:
    if not chunks:
        return {"count": 0, "avg_chars": 0, "max_chars": 0, "min_chars": 0}
    lens = [len(c.raw_text) for c in chunks]
    return {
        "count": len(chunks),
        "avg_chars": round(sum(lens) / len(lens), 1),
        "max_chars": max(lens),
        "min_chars": min(lens),
    }
