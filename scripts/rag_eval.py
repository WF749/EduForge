#!/usr/bin/env python
"""RAG 评测 CLI（对应 `make eval`）。

用法
----
    python scripts/rag_eval.py                  # 用当前索引跑 100 条评测集
    python scripts/rag_eval.py --reindex        # 先用 knowledge_base/ 重建索引再评
    python scripts/rag_eval.py --no-rerank      # 只测混合检索，不测重排
    python scripts/rag_eval.py --verbose        # 逐条打印
    python scripts/rag_eval.py --sweep          # 扫描阈值，给出最佳阈值建议
    python scripts/rag_eval.py --json out.json  # 导出机器可读结果
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))


def reindex(kb_dir: Path) -> int:
    """用 knowledge_base/ 下的 md/txt 重建索引。"""
    from app.rag.retriever import get_retriever

    r = get_retriever()
    r.clear()
    n = 0
    for f in sorted(list(kb_dir.glob("*.md")) + list(kb_dir.glob("*.txt"))):
        st = r.add_document(
            f.stem, f.read_text(encoding="utf-8"),
            {"filename": f.name, "source": "seed"},
        )
        print(f"  索引 {f.name}: {st['chunks']} chunks, 向量={st['vector_indexed']}")
        n += st["chunks"]
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description="EduForge RAG 评测")
    ap.add_argument("--evalset", default="evals/rag_eval_set.jsonl")
    ap.add_argument("--kb", default="knowledge_base")
    ap.add_argument("--reindex", action="store_true", help="先重建索引")
    ap.add_argument("--no-rerank", action="store_true")
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--min-vector", type=float, default=None)
    ap.add_argument("--min-rerank", type=float, default=None)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--sweep", action="store_true", help="扫描拒答阈值")
    ap.add_argument("--json", dest="json_out", default="")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]

    if args.reindex:
        print("重建索引 …")
        n = reindex(root / args.kb)
        print(f"索引完成，共 {n} 个片段\n")

    from app.rag.evalset import RAGEvaluator, format_report, load_evalset
    from app.rag.retriever import get_retriever

    items = load_evalset(root / args.evalset)
    print(f"载入评测集：{len(items)} 条\n")

    ev = RAGEvaluator(get_retriever())
    extra = {}
    if args.min_vector is not None:
        extra['min_vector'] = args.min_vector
    if args.min_rerank is not None:
        extra['min_rerank'] = args.min_rerank
    metrics = ev.run(
        items, top_k=args.top_k, enable_rerank=not args.no_rerank,
        verbose=args.verbose, **extra,
    )
    print(format_report(metrics))

    if args.sweep:
        # 评分权重说明：两类错误的代价不对等。
        #   漏拒（该拒却放行）→ 模型拿着无关上下文硬答 → **编造**，教师会拿到错误信息，最危险；
        #   误拒（可答却拒了）→ 只是答不上来，安全但体验差。
        # 因此漏拒按 3 倍权重惩罚，不能简单用"准确率 + 召回"平均。
        # 扫描是**零额外检索成本**的：检索只做一次（collect），
        # 之后每个阈值都在留档分数上重算。本地 cross-encoder 重排
        # 单次 ~800ms，若按老办法每个阈值重跑一遍，100 条 × 9 档要 12 分钟。
        label = "rerank 阈值" if not args.no_rerank else "向量阈值"
        grid = ([0.30, 0.40, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]
                if not args.no_rerank
                else [0.30, 0.35, 0.40, 0.45, 0.48, 0.50, 0.55, 0.60])
        kw_name = "min_rerank" if not args.no_rerank else "min_vector"
        print(f"\n{label}扫描（检索一次后在留档分数上重算；漏拒按 3 倍权重惩罚）：")
        collected = ev.collect(items, top_k=args.top_k,
                               enable_rerank=not args.no_rerank)
        print(f"  已留档 {len(collected['rows'])} 条检索结果")
        print(f"  {'阈值':>6} {'Recall@1':>9} {'拒答准确率':>10} {'误拒':>7} {'漏拒':>7} {'加权分':>8}")
        best = None
        for th in grid:
            m = ev.evaluate_at(collected, **{kw_name: th})
            acc = m["refusal"]["accuracy"]
            false_r = m["refusal"]["false_refusal"]
            missed = m["refusal"]["missed_refusal"]
            score = m["retrieval"]["recall@1"] - 3.0 * missed - 1.0 * false_r
            print(f"  {th:>6.2f} {m['retrieval']['recall@1']:>9.3f} "
                  f"{acc:>10.3f} {false_r:>7.3f} {missed:>7.3f} {score:>8.3f}")
            if best is None or score > best[1]:
                best = (th, score)
        if best:
            print(f"\n  最佳阈值建议: {best[0]:.2f}（加权分 {best[1]:.3f}）")

    if args.json_out:
        out = root / args.json_out
        out.write_text(json.dumps(metrics, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        print(f"\n结果已写入 {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
