"""BM25 关键词检索 —— 纯 Python 实现，无第三方依赖。

为什么不用现成库
----------------
`rank_bm25` / `whoosh` 都要额外安装，且不支持中文分词。
这里不到 150 行就能跑，中文分词优先用 jieba，缺失时自动降级为
**字符二元组**（对中文而言二元组已能覆盖大部分词面匹配，
实测在教学资料短文本上召回与 jieba 接近，但零依赖）。

BM25 公式（k1=1.5, b=0.75 为经典取值）
    score(q, d) = Σ_t IDF(t) * (f(t,d) * (k1+1)) / (f(t,d) + k1*(1-b+b*|d|/avgdl))
"""

from __future__ import annotations

import math
import re
from typing import Dict, List, Sequence

# ---------------------------------------------------------------------------
# 分词
# ---------------------------------------------------------------------------

_CJK = re.compile(r"[\u4e00-\u9fff]")
_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]")

try:
    import jieba  # type: ignore

    _HAS_JIEBA = True
except Exception:  # pragma: no cover - jieba 缺失是允许的降级路径
    jieba = None  # type: ignore
    _HAS_JIEBA = False


def _char_bigrams(text: str) -> List[str]:
    """字符二元组分词（中文降级方案）。"""
    out: List[str] = []
    for m in _TOKEN_RE.findall(text):
        m = m.lower()
        if _CJK.match(m):
            out.append(m)
        elif len(m) > 1:
            out.append(m)
    # 中文连续片段生成二元组
    cjk_runs = re.findall(r"[\u4e00-\u9fff]+", text)
    for run in cjk_runs:
        if len(run) == 1:
            out.append(run)
        for i in range(len(run) - 1):
            out.append(run[i : i + 2])
    return out


def tokenize(text: str, *, for_index: bool = False) -> List[str]:
    """中文/英文混合分词。

    for_index=True 时会额外补充二元组，提高短查询的词面命中率
    （仅用于建索引，不影响查询侧，避免查询被过度扩展）。
    """
    if not text:
        return []
    text = text.lower()
    if _HAS_JIEBA:
        toks = [t.strip() for t in jieba.cut(text) if t.strip()]
        # 过滤纯标点与单字符空白
        toks = [t for t in toks if _TOKEN_RE.fullmatch(t) or len(t) > 1]
        if for_index:
            # 索引侧补二元组：查询"牛顿第二定律"也能命中"牛顿/第二/定律"的任意组合
            toks += _char_bigrams(text)
        return toks
    return _char_bigrams(text)


# ---------------------------------------------------------------------------
# BM25
# ---------------------------------------------------------------------------

class BM25:
    """增量可重建的 BM25 索引。

    设计为「可整体重建」而非「增量追加」：教学知识库规模是百到千级文档，
    全量重建在毫秒级完成，比维护增量结构更简单也更不容易出错。
    """

    K1 = 1.5
    B = 0.75

    def __init__(self) -> None:
        self.doc_ids: List[str] = []
        self.doc_len: List[int] = []
        self.tf: List[Dict[str, int]] = []
        self.df: Dict[str, int] = {}
        self.avgdl: float = 0.0
        self._idf_cache: Dict[str, float] = {}

    # -- 构建 ---------------------------------------------------------------
    def build(self, doc_ids: Sequence[str], texts: Sequence[str]) -> None:
        self.doc_ids = list(doc_ids)
        self.doc_len = []
        self.tf = []
        self.df = {}
        self._idf_cache = {}

        for text in texts:
            toks = tokenize(text, for_index=True)
            counts: Dict[str, int] = {}
            for t in toks:
                counts[t] = counts.get(t, 0) + 1
            self.tf.append(counts)
            self.doc_len.append(len(toks))
            for t in counts:
                self.df[t] = self.df.get(t, 0) + 1

        n = len(self.doc_ids)
        self.avgdl = (sum(self.doc_len) / n) if n else 0.0

    # -- 检索 ---------------------------------------------------------------
    def _idf(self, term: str) -> float:
        if term in self._idf_cache:
            return self._idf_cache[term]
        n = len(self.doc_ids)
        df = self.df.get(term, 0)
        # BM25 经典 IDF，+0.5 平滑避免负值
        val = math.log(1.0 + (n - df + 0.5) / (df + 0.5)) if n else 0.0
        self._idf_cache[term] = val
        return val

    def search(self, query: str, top_k: int = 20) -> List[tuple]:
        """返回 [(doc_id, score), ...]，按分数降序。"""
        if not self.doc_ids:
            return []
        q_tokens = tokenize(query)
        if not q_tokens:
            return []

        scores: List[float] = [0.0] * len(self.doc_ids)
        for qt in set(q_tokens):
            idf = self._idf(qt)
            if idf <= 0:
                continue
            for i, counts in enumerate(self.tf):
                f = counts.get(qt, 0)
                if not f:
                    continue
                dl = self.doc_len[i] or 1
                denom = f + self.K1 * (1 - self.B + self.B * dl / (self.avgdl or 1.0))
                scores[i] += idf * (f * (self.K1 + 1)) / denom

        ranked = sorted(
            ((self.doc_ids[i], s) for i, s in enumerate(scores) if s > 0),
            key=lambda x: x[1],
            reverse=True,
        )
        return ranked[:top_k]

    @property
    def size(self) -> int:
        return len(self.doc_ids)


def backend_name() -> str:
    return "jieba" if _HAS_JIEBA else "char-bigram"
