"""RAG 评测 —— 没有度量就没有改进。

指标设计说明（为什么不完全照搬 RAGAS）
--------------------------------------
RAGAS 的 `faithfulness` / `answer_relevancy` 需要额外调用大模型逐条打分，
100 条评测集意味着 100+ 次 LLM 调用，既慢又烧钱，且分数受评委模型影响。

因此这里拆成两层：

**第一层（默认，零成本，可 CI 化）** —— 纯检索指标：
  Recall@k     期望来源文档是否出现在 top-k（衡量"找没找到"）
  MRR@5        首个正确结果的排名倒数的均值（衡量"排得够不够前"）
  TermHit@1    top-1 片段是否包含期望的关键信息（衡量"给模型的是不是对的片段"）
  RefusalAcc   拒答准确率（可答的没误拒 + 不可答的正确拒答）
  延迟 p50/p95

**第二层（可选，--with-llm）** —— 生成质量 LLM-as-judge：
  Faithfulness   回答中的事实是否都能在检索到的上下文里找到依据（防编造）
  AnswerRelevancy 回答是否真的回应了问题

第二层默认关闭：它要花钱，且结果依赖评委模型，不应混进日常回归指标。
"""

from __future__ import annotations

import json
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .retriever import (
    DEFAULT_MIN_BM25,
    DEFAULT_MIN_RERANK,
    DEFAULT_MIN_VECTOR,
    HybridRetriever,
    RetrievalResult,
)

# parents 层级：backend/app/rag/evalset.py → [0]=rag [1]=app [2]=backend [3]=仓库根
DEFAULT_EVALSET = (
    Path(__file__).resolve().parents[3] / "evals" / "rag_eval_set.jsonl"
)


@dataclass
class EvalItem:
    id: str
    query: str
    answerable: bool
    expect_source: str = ""
    expect_terms: List[str] = field(default_factory=list)
    # 有些概念在多篇文档里都真实存在（如"控制结构"既在 Python 文档也在示例文档），
    # 此时任何一篇都算正确，强行指定单一来源只会把标注噪声算成模型错误。
    expect_sources: List[str] = field(default_factory=list)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "EvalItem":
        single = str(d.get("expect_source") or "")
        return EvalItem(
            id=str(d.get("id") or ""),
            query=str(d.get("query") or "").strip(),
            answerable=bool(d.get("answerable", True)),
            expect_source=single,
            expect_terms=list(d.get("expect_terms") or []),
            expect_sources=list(d.get("expect_sources") or ([single] if single else [])),
        )


def load_evalset(path: Optional[Path] = None) -> List[EvalItem]:
    p = Path(path) if path else DEFAULT_EVALSET
    items: List[EvalItem] = []
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            items.append(EvalItem.from_dict(json.loads(line)))
    return items


# ---------------------------------------------------------------------------
# 判定
# ---------------------------------------------------------------------------

def _norm_sources(item_or_str: Any) -> List[str]:
    """统一取期望来源列表，兼容 str 与 list 两种标注写法。"""
    if isinstance(item_or_str, str):
        return [item_or_str] if item_or_str else []
    return [s for s in (item_or_str or []) if s]


def _src_in(source: str, expects: Sequence[str]) -> bool:
    """单个命中来源是否落在期望来源集合内。"""
    src = source or ""
    return any(src == e or src.startswith(e) for e in expects if e)


def _source_hit(result: RetrievalResult, expect: Any, k: int) -> bool:
    expects = _norm_sources(expect)
    if not expects:
        return False
    for h in result.hits[:k]:
        src = h.source or ""
        if any(src == e or src.startswith(e) for e in expects):
            return True
    return False


def _term_hit(result: RetrievalResult, terms: Sequence[str], k: int = 1) -> bool:
    """top-k 片段里是否包含任一期望关键信息。"""
    if not terms:
        return True
    pool = "\n".join((h.text or "") for h in result.hits[:k])
    return any(t in pool for t in terms)


def _reciprocal_rank(result: RetrievalResult, expect: Any, k: int = 5) -> float:
    expects = _norm_sources(expect)
    if not expects:
        return 0.0
    for i, h in enumerate(result.hits[:k], 1):
        src = h.source or ""
        if any(src == e or src.startswith(e) for e in expects):
            return 1.0 / i
    return 0.0


# ---------------------------------------------------------------------------
# 执行器
# ---------------------------------------------------------------------------

class RAGEvaluator:
    def __init__(self, retriever: Optional[HybridRetriever] = None) -> None:
        self.retriever = retriever

    def run(
        self,
        items: Sequence[EvalItem],
        *,
        top_k: int = 5,
        enable_rerank: bool = True,
        min_vector: Optional[float] = None,
        min_rerank: Optional[float] = None,
        verbose: bool = False,
    ) -> Dict[str, Any]:
        r = self.retriever
        assert r is not None, "需要提供 retriever"

        kw = {}
        if min_vector is not None:
            kw["min_vector"] = min_vector
        if min_rerank is not None:
            kw["min_rerank"] = min_rerank

        rows: List[Dict[str, Any]] = []
        latencies: List[float] = []

        for item in items:
            res = r.retrieve(
                item.query, top_k=top_k, enable_rerank=enable_rerank, **kw
            )
            latencies.append(res.elapsed_ms)

            if item.answerable:
                recall = {k: _source_hit(res, item.expect_sources, k)
                          for k in (1, 3, 5)}
                rr = _reciprocal_rank(res, item.expect_sources, 5)
                term = _term_hit(res, item.expect_terms, 1)
                # 可答题被拒答 = 误拒（false refusal）
                refusal_ok = not res.refused
            else:
                recall = {1: False, 3: False, 5: False}
                rr = 0.0
                term = True
                # 不可答题必须拒答
                refusal_ok = res.refused

            rows.append({
                "id": item.id,
                "query": item.query,
                "answerable": item.answerable,
                "expect_source": " | ".join(item.expect_sources),
                "recall@1": recall[1], "recall@3": recall[3], "recall@5": recall[5],
                "rr": rr,
                "term_hit": term,
                "refused": res.refused,
                "refusal_ok": refusal_ok,
                "rerank_backend": res.rerank_backend,
                "top_source": (res.hits[0].source if res.hits else ""),
                "top_score": (res.hits[0].score if res.hits else 0.0),
                "top_vector": (res.hits[0].vector_score if res.hits else 0.0),
                "latency_ms": res.elapsed_ms,
            })
            if verbose:
                flag = "OK " if (refusal_ok and (not item.answerable or recall[1])) else "MISS"
                print(f"  [{flag}] {item.id} {item.query[:28]:30s} -> "
                      f"{(rows[-1]['top_source'] or '(拒答)')[:34]}")

        return self._aggregate(rows, latencies, top_k=top_k,
                               enable_rerank=enable_rerank)

    def collect(
        self,
        items: Sequence[EvalItem],
        *,
        top_k: int = 5,
        enable_rerank: bool = True,
    ) -> Dict[str, Any]:
        """**只检索一次**，把判定所需的原始分数全部留档。

        为什么需要它：阈值扫描按理要 `阈值数 × 样本数` 次检索。
        向量/BM25 通道只要 13ms，重来无妨；但本地 cross-encoder 重排
        单次就要 ~800ms，100 条 × 9 个阈值 = 12 分钟，慢到没人愿意跑。

        而阈值**不影响**候选集与排序，只影响最终是否拒答。
        所以这里把拒答闸门关掉（阈值设为 -1）跑一遍，
        拿到每条的 best_rerank / best_vector / best_bm25 与命中结果，
        之后扫阈值就是在这些留档分数上做纯计算，零额外检索成本。
        """
        r = self.retriever
        assert r is not None, "需要提供 retriever"

        rows: List[Dict[str, Any]] = []
        for item in items:
            res = r.retrieve(
                item.query, top_k=top_k, enable_rerank=enable_rerank,
                min_rerank=-1.0, min_vector=-1.0, min_bm25=-1.0,
            )
            rows.append({
                "item": item,
                "hits": res.hits,
                "best_rerank": res.best_rerank,
                "best_vector": res.best_vector,
                "best_bm25_raw": res.best_bm25_raw,
                "rerank_backend": res.rerank_backend,
                "latency_ms": res.elapsed_ms,
                "empty": not res.hits,
            })
        return {"rows": rows, "top_k": top_k, "enable_rerank": enable_rerank}

    @staticmethod
    def evaluate_at(collected: Dict[str, Any], **thresholds) -> Dict[str, Any]:
        """在 `collect()` 的留档结果上，用给定阈值算一遍指标（零检索成本）。"""
        rows = collected["rows"]
        top_k = collected["top_k"]
        min_rerank = float(thresholds.get("min_rerank", DEFAULT_MIN_RERANK))
        min_vector = float(thresholds.get("min_vector", DEFAULT_MIN_VECTOR))
        min_bm25 = float(thresholds.get("min_bm25", DEFAULT_MIN_BM25))

        evals: List[Dict[str, Any]] = []
        for row in rows:
            item: EvalItem = row["item"]
            # 复刻 retriever 的判定顺序：rerank > 向量 > BM25
            if row["empty"]:
                refused = True
            elif row["best_rerank"] is not None:
                refused = row["best_rerank"] < min_rerank
            elif row["best_vector"] > 0:
                refused = row["best_vector"] < min_vector
            else:
                refused = row["best_bm25_raw"] < min_bm25

            hits = [] if refused else row["hits"]

            if item.answerable:
                expect = item.expect_sources
                hit1 = any(_src_in(h.source, expect) for h in hits[:1])
                hit3 = any(_src_in(h.source, expect) for h in hits[:3])
                hit5 = any(_src_in(h.source, expect) for h in hits[:5])
                rr = 0.0
                for i, h in enumerate(hits[:5], 1):
                    if _src_in(h.source, expect):
                        rr = 1.0 / i
                        break
                term = (not item.expect_terms) or any(
                    t in "\n".join(h.text for h in hits[:1]) for t in item.expect_terms
                )
                refusal_ok = not refused
            else:
                hit1 = hit3 = hit5 = False
                rr = 0.0
                term = True
                refusal_ok = refused

            evals.append({
                "id": item.id, "query": item.query, "answerable": item.answerable,
                "expect_source": " | ".join(item.expect_sources),
                "recall@1": hit1, "recall@3": hit3, "recall@5": hit5,
                "rr": rr, "term_hit": term, "refused": refused,
                "refusal_ok": refusal_ok,
                "rerank_backend": row["rerank_backend"],
                "top_source": (hits[0].source if hits else ""),
                "top_score": (hits[0].score if hits else 0.0),
                "top_vector": (hits[0].vector_score if hits else 0.0),
                "latency_ms": row["latency_ms"],
            })

        return RAGEvaluator._aggregate(
            evals, [r_["latency_ms"] for r_ in evals],
            top_k=top_k, enable_rerank=collected["enable_rerank"],
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _aggregate(
        rows: List[Dict[str, Any]], latencies: List[float], *,
        top_k: int, enable_rerank: bool,
    ) -> Dict[str, Any]:
        ans = [r_ for r_ in rows if r_["answerable"]]
        unans = [r_ for r_ in rows if not r_["answerable"]]
        n_ans = len(ans) or 1
        n_un = len(unans) or 1

        def rate(subset, key):
            return sum(1 for r_ in subset if r_[key]) / (len(subset) or 1)

        sorted_lat = sorted(latencies)
        pct = lambda p: (  # noqa: E731
            sorted_lat[min(len(sorted_lat) - 1, int(len(sorted_lat) * p))]
            if sorted_lat else 0.0
        )

        return {
            "total": len(rows),
            "answerable": len(ans),
            "unanswerable": len(unans),
            "retrieval": {
                "recall@1": round(rate(ans, "recall@1"), 4),
                "recall@3": round(rate(ans, "recall@3"), 4),
                "recall@5": round(rate(ans, "recall@5"), 4),
                "mrr@5": round(sum(r_["rr"] for r_ in ans) / n_ans, 4),
                "term_hit@1": round(rate(ans, "term_hit"), 4),
            },
            "refusal": {
                "accuracy": round(rate(rows, "refusal_ok"), 4),
                "false_refusal": round(
                    sum(1 for r_ in ans if r_["refused"]) / n_ans, 4),
                "missed_refusal": round(
                    sum(1 for r_ in unans if not r_["refused"]) / n_un, 4),
            },
            "latency_ms": {
                "p50": round(pct(0.50), 1),
                "p95": round(pct(0.95), 1),
                "mean": round(statistics.mean(latencies), 1) if latencies else 0.0,
            },
            "config": {
                "top_k": top_k,
                "enable_rerank": enable_rerank,
                "rerank_backends": sorted({r_["rerank_backend"] for r_ in rows}),
            },
            "failures": [
                {
                    "id": r_["id"], "query": r_["query"],
                    "expect": r_["expect_source"], "got": r_["top_source"],
                    "refused": r_["refused"],
                    "score": round(r_["top_score"], 3),
                    "vector": round(r_["top_vector"], 3),
                }
                for r_ in rows
                if not r_["refusal_ok"] or (r_["answerable"] and not r_["recall@1"])
            ],
        }


def format_report(m: Dict[str, Any]) -> str:
    r = m["retrieval"]
    f = m["refusal"]
    l = m["latency_ms"]
    lines = [
        "=" * 62,
        "  RAG 评测报告",
        "=" * 62,
        f"  样本: {m['total']} 条（可答 {m['answerable']} / 应拒答 {m['unanswerable']}）",
        "",
        "  【检索质量 — 零成本核心指标】",
        f"    Recall@1   {r['recall@1']:.3f}",
        f"    Recall@3   {r['recall@3']:.3f}",
        f"    Recall@5   {r['recall@5']:.3f}",
        f"    MRR@5      {r['mrr@5']:.3f}",
        f"    TermHit@1  {r['term_hit@1']:.3f}   (top-1 含期望关键信息)",
        "",
        "  【拒答质量 — 防止编造的最后一道闸】",
        f"    拒答准确率    {f['accuracy']:.3f}",
        f"    误拒率        {f['false_refusal']:.3f}   (可答却被拒)",
        f"    漏拒率        {f['missed_refusal']:.3f}   (该拒却放行 → 会导致编造)",
        "",
        f"  【延迟】 p50 {l['p50']}ms  p95 {l['p95']}ms  mean {l['mean']}ms",
        f"  【配置】 top_k={m['config']['top_k']}  rerank={m['config']['rerank_backends']}",
    ]
    if m["failures"]:
        lines += ["", f"  【未达标 {len(m['failures'])} 条】"]
        for f_ in m["failures"][:15]:
            reason = "误拒" if f_["refused"] else "排错"
            lines.append(
                f"    {f_['id']} [{reason}] {f_['query'][:26]:28s}"
                f" 期望={f_['expect'][:20]:22s} 实际={f_['got'][:24]}"
                f" vec={f_['vector']:.2f}"
            )
        if len(m["failures"]) > 15:
            lines.append(f"    … 另有 {len(m['failures']) - 15} 条")
    lines += ["=" * 62]
    return "\n".join(lines)
