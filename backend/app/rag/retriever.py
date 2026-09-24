"""混合检索主入口 —— RAG 全链路的中枢。

流程
----
    查询
      ├─ 向量通道（bge-small-zh-v1.5，Chroma 持久化）
      └─ 关键词通道（BM25，中文分词）
           ↓ RRF 融合（Reciprocal Rank Fusion，k=60）
        候选集（取两通道并集的 top-N）
           ↓ 重排序（rerank，可降级）
        阈值判定 → **低于阈值直接拒答**，不把无关上下文塞给模型
           ↓
    结果 + 引用溯源（来源文件 / 标题路径 / 原文片段）

为什么用 RRF 而不是加权求和
--------------------------
向量分（余弦，约 0~1）与 BM25 分（无上界）量纲不同，
加权求和需要先归一化，而归一化系数会随语料漂移。
RRF 只用**排名**，天然量纲无关，且对单一通道的分数抖动不敏感，
是工程上更稳的做法。
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from ..core.logging_setup import get_logger
from ..core.observability import Span, metrics
from .bm25 import BM25, backend_name
from .chunker import chunk_document, chunk_stats
from .embeddings import embed_status, get_embedding
from .rerank import MODEL_ID as RERANK_MODEL_ID, get_reranker

log = get_logger("rag.retriever")

# 与旧 collection 区分：bge 是 512 维，旧的 all-MiniLM 是 384 维，
# 混用会导致 Chroma 维度不匹配错误。
COLLECTION_NAME = "eduforge_rag_v2"
RRF_K = 60

# 阈值由 evals/rag_eval_set.jsonl 实测标定（见 `make eval`），不是拍脑袋定的。
#
# 关键教训：**不要用批内归一化后的 BM25 分做阈值**。
# 归一化是相对当前候选集的，当所有候选都是噪声时，最差的那个也会被拉到 1.0，
# 导致"知识库里根本没有"的查询被判定为强命中（曾出现「太阳系有几颗行星」
# 因"行/星"二字命中酒店礼貌用语而被放行）。
# 因此阈值一律基于**绝对分**：向量余弦、rerank 分、或 BM25 原始分。
# 向量阈值几乎无效，必须靠 rerank：
# 实测可答题的向量余弦落在 0.36~0.78，而"量子力学的不确定性原理"这种
# 语料里完全没有的查询反而拿到 0.49 —— 两簇重叠，**任何向量阈值都切不开**。
# 这也是本项目坚持做 rerank 的原因，不是为了堆技术栈。
DEFAULT_MIN_VECTOR = 0.45       # 仅在 rerank 不可用时的兜底
# rerank 阈值标定（100 条评测集，可答 90 / 应拒答 10）。
#
# **阈值与 rerank 后端强绑定，换后端必须重新标定。** 这不是理论洁癖，
# 是踩出来的：本地 bge-reranker-base 输出 logit，经 sigmoid 后无关样本
# 集中在 0.50 附近（logit≈0），相关样本 0.55~0.99；而百炼 qwen3-rerank
# 的可答题最低 0.421、应拒答题最高 0.365。两者分位完全不同 ——
# 沿用为云端标定的 0.39 时，**10 条该拒的查询一条都没拦住（漏拒率 1.000）**。
#
# 本地模型实测扫描（漏拒按 3 倍权重惩罚，因为漏拒会导致模型编造）：
#   0.50 → 漏拒 1.000      0.55 → 漏拒 0.000 误拒 0.022  ← 最优
#   0.60 → 误拒 0.067      0.75 → 全部拒答（sigmoid 饱和，悬崖式劣化）
# 0.55 距下悬崖（0.75）有 0.20 余量，距产生漏拒的 0.50 有 0.05 余量。
DEFAULT_MIN_RERANK = 0.55
DEFAULT_MIN_BM25 = 4.0          # 仅当向量与 rerank 都不可用时的兜底
DEFAULT_TOP_K = 5
DEFAULT_CANDIDATES = 20


# ---------------------------------------------------------------------------
# 来源标记（origin）
# ---------------------------------------------------------------------------
# 只此一处定义，全项目共用。此前**同一个意思用了两个字段**：
# 种子文档写 `source="seed"`，上传文档写 `origin="upload"`；
# 而 `knowledge_store.clear_all()` 是按 `origin` 过滤的，
# 于是种子文档靠"恰好没有 origin"侥幸存活 —— 任何一处改字段名就会误删或漏删。
#
# 约定：
#   * `origin` = 来源分类，只有 seed / upload 两种，用于"能删什么、不能删什么"；
#   * `source` = 展示用的来源名（种子是 "seed"，上传是文件名）；
#   * `filename` = 原始文件名（种子为 md 文件名，上传为用户上传名）。
ORIGIN_SEED = "seed"
ORIGIN_UPLOAD = "upload"


def is_seed_metadata(metadata: Optional[Dict[str, Any]]) -> bool:
    """判定一篇文档是不是种子语料。

    历史遗留：早期只写 `source="seed"` 不写 `origin`。两种都认，
    这样老索引在下次 reindex / 启动同步时会被识别并补上 `origin`，
    不会变成"谁都删不掉也认不出"的孤儿文档。
    """
    meta = metadata or {}
    return meta.get("origin") == ORIGIN_SEED or meta.get("source") == ORIGIN_SEED


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class RetrievalHit:
    chunk_id: str
    text: str                 # 含标题前缀（用于喂模型）
    raw_text: str             # 原文（用于展示）
    score: float              # 最终融合/重排分（排序用）
    vector_score: float = 0.0  # 余弦相似度，绝对分 [−1,1]
    bm25_score: float = 0.0    # 批内归一化的展示分 [0,1]，**不可用于阈值判定**
    bm25_raw: float = 0.0      # BM25 原始分，绝对分，兜底阈值用
    rerank_score: Optional[float] = None
    source: str = ""          # 来源文件名
    heading_path: str = ""
    chunk_index: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "raw_text": self.raw_text,
            "score": round(self.score, 4),
            "vector_score": round(self.vector_score, 4),
            "bm25_score": round(self.bm25_score, 4),
            "bm25_raw": round(self.bm25_raw, 4),
            "rerank_score": None if self.rerank_score is None else round(self.rerank_score, 4),
            "source": self.source,
            "heading_path": self.heading_path,
            "chunk_index": self.chunk_index,
            "metadata": self.metadata,
        }

    def citation(self) -> str:
        """人可读的引用标签，如「03_高中英语_阅读理解技巧.md · 题型分类 > 主旨大意题」。"""
        if self.heading_path:
            return f"{self.source} · {self.heading_path}"
        return self.source


@dataclass
class RetrievalResult:
    query: str
    hits: List[RetrievalHit] = field(default_factory=list)
    refused: bool = False
    refuse_reason: str = ""
    degraded: bool = False
    degrade_reasons: List[str] = field(default_factory=list)
    rerank_backend: str = "none"
    channels: Dict[str, int] = field(default_factory=dict)
    elapsed_ms: float = 0.0
    # 诊断字段：即使拒答（hits 被清空）也保留各通道最优分，
    # 否则线上出现误拒时无从定位到底是阈值太严还是召回就错了。
    best_vector: float = 0.0
    best_bm25_raw: float = 0.0
    best_rerank: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "hits": [h.to_dict() for h in self.hits],
            "refused": self.refused,
            "refuse_reason": self.refuse_reason,
            "degraded": self.degraded,
            "degrade_reasons": self.degrade_reasons,
            "rerank_backend": self.rerank_backend,
            "channels": self.channels,
            "elapsed_ms": round(self.elapsed_ms, 2),
            "best_vector": round(self.best_vector, 4),
            "best_bm25_raw": round(self.best_bm25_raw, 4),
            "best_rerank": (None if self.best_rerank is None
                            else round(self.best_rerank, 4)),
        }

    def context_block(self, max_chars: int = 3000) -> str:
        """拼成可直接注入 prompt 的上下文块，带 [1][2] 编号便于模型标注引用。"""
        if self.refused or not self.hits:
            return ""
        lines = ["【知识库参考资料】"]
        refs: List[str] = []
        used = 0
        for i, h in enumerate(self.hits, 1):
            frag = h.raw_text[:600]
            if used + len(frag) > max_chars and refs:
                break
            lines.append(f"[{i}] {frag}")
            refs.append(f"[{i}] {h.citation()}")
            used += len(frag)
        lines.append("来源：" + "；".join(refs))
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 检索器
# ---------------------------------------------------------------------------

class HybridRetriever:
    """向量 + BM25 混合检索。

    索引由两部分组成，可互相重建：
      * **Chroma**：向量（embedding 不可用时可缺失）
      * **JSON 侧车**：chunk 文本与元数据（BM25 的来源，也是向量的重建依据）
    """

    def __init__(self, index_dir: Optional[Path] = None) -> None:
        # 注意 parents 层级：本文件在 backend/app/rag/ → parents[2] 才是 backend/
        self.index_dir = Path(index_dir) if index_dir else (
            Path(__file__).resolve().parents[2] / "data" / "rag_index"
        )
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.chunks_file = self.index_dir / "chunks.json"
        self.meta_file = self.index_dir / "documents.json"

        self._lock = threading.RLock()
        self.chunks: Dict[str, Dict[str, Any]] = {}
        self.documents: Dict[str, Dict[str, Any]] = {}
        self._bm25: Optional[BM25] = None
        self._chroma = None
        self._collection = None
        self._chroma_ready = False
        self._chroma_error = ""

        self._load()

    # ------------------------------------------------------------------
    # 持久化
    # ------------------------------------------------------------------
    def _load(self) -> None:
        if self.chunks_file.exists():
            try:
                self.chunks = json.loads(self.chunks_file.read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001
                log.warning("rag 索引读取失败，重建空索引: %s", e)
                self.chunks = {}
        if self.meta_file.exists():
            try:
                self.documents = json.loads(self.meta_file.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                self.documents = {}
        self._rebuild_bm25()

    def _save(self) -> None:
        tmp = self.chunks_file.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(self.chunks, ensure_ascii=False, indent=0), encoding="utf-8"
        )
        tmp.replace(self.chunks_file)
        tmp2 = self.meta_file.with_suffix(".json.tmp")
        tmp2.write_text(
            json.dumps(self.documents, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        tmp2.replace(self.meta_file)

    def _rebuild_bm25(self) -> None:
        if not self.chunks:
            self._bm25 = BM25()
            return
        ids = list(self.chunks.keys())
        texts = [(self.chunks[i].get("text") or "") for i in ids]
        bm = BM25()
        bm.build(ids, texts)
        self._bm25 = bm

    # ------------------------------------------------------------------
    # Chroma
    # ------------------------------------------------------------------
    def _ensure_chroma(self) -> bool:
        if self._chroma_ready:
            return True
        if self._chroma_error:
            return False
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            persist_dir = str(self.index_dir / "chroma")
            Path(persist_dir).mkdir(parents=True, exist_ok=True)
            self._chroma = chromadb.PersistentClient(
                path=persist_dir, settings=ChromaSettings(anonymized_telemetry=False)
            )
            self._collection = self._chroma.get_or_create_collection(
                name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
            )
            self._chroma_ready = True
            return True
        except Exception as e:  # noqa: BLE001
            self._chroma_error = f"{type(e).__name__}: {e}"
            log.warning("Chroma 不可用，向量通道降级: %s", self._chroma_error)
            return False

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------
    @staticmethod
    def _chunk_id(document_id: str, idx: int, text: str) -> str:
        h = hashlib.sha1(f"{document_id}::{idx}::{text[:64]}".encode("utf-8")).hexdigest()
        return f"c_{h[:24]}"

    def add_document(
        self,
        document_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        *,
        chunk_size: int = 320,
        chunk_overlap: int = 60,
    ) -> Dict[str, Any]:
        """索引一篇文档。已存在则先删除旧索引再重建（保证幂等）。"""
        if not content or not content.strip():
            return {"document_id": document_id, "chunks": 0, "skipped": "empty"}

        with self._lock:
            self.delete_document(document_id, save=False)

            chunks = chunk_document(
                content, chunk_size=chunk_size, chunk_overlap=chunk_overlap,
                source=document_id,
            )
            meta = dict(metadata or {})
            ids: List[str] = []
            texts: List[str] = []
            metas: List[Dict[str, Any]] = []

            for c in chunks:
                cid = self._chunk_id(document_id, c.chunk_index, c.raw_text)
                record = {
                    "chunk_id": cid,
                    "text": c.text,
                    "raw_text": c.raw_text,
                    "heading_path": c.heading_path,
                    "chunk_index": c.chunk_index,
                    "source": document_id,
                    "char_start": c.char_start,
                    "char_end": c.char_end,
                    "metadata": dict(meta),
                }
                self.chunks[cid] = record
                ids.append(cid)
                texts.append(c.text)
                metas.append({
                    "source": document_id,
                    "heading_path": c.heading_path,
                    "chunk_index": c.chunk_index,
                    **{k: v for k, v in meta.items() if isinstance(v, (str, int, float, bool))},
                })

            # 向量写入（失败不阻断：BM25 仍可用）
            vector_ok = False
            vector_reason = ""
            emb = get_embedding()
            if emb.available or getattr(emb, "_ensure", None):
                try:
                    vecs = emb.encode_documents(texts)
                    if self._ensure_chroma() and self._collection is not None:
                        self._collection.upsert(
                            ids=ids, documents=texts,
                            embeddings=[v.tolist() for v in vecs], metadatas=metas,
                        )
                        vector_ok = True
                    else:
                        vector_reason = self._chroma_error or "Chroma 不可用"
                except Exception as e:  # noqa: BLE001
                    vector_reason = f"{type(e).__name__}: {e}"
                    log.warning("向量写入失败（仅保留关键词索引）: %s", vector_reason)
            else:
                vector_reason = emb.reason or "embedding 不可用"

            self.documents[document_id] = {
                "document_id": document_id,
                "chunks": len(ids),
                "chars": len(content),
                "indexed_at": time.time(),
                "vector_indexed": vector_ok,
                "metadata": meta,
            }
            self._rebuild_bm25()
            self._save()

            return {
                "document_id": document_id,
                "chunks": len(ids),
                "vector_indexed": vector_ok,
                "vector_reason": vector_reason,
                "stats": chunk_stats(chunks),
            }

    def delete_document(self, document_id: str, save: bool = True) -> int:
        with self._lock:
            to_del = [
                cid for cid, c in self.chunks.items()
                if c.get("source") == document_id
            ]
            for cid in to_del:
                self.chunks.pop(cid, None)
            if to_del and self._ensure_chroma() and self._collection is not None:
                try:
                    self._collection.delete(ids=to_del)
                except Exception as e:  # noqa: BLE001
                    log.warning("向量删除失败: %s", e)
            self.documents.pop(document_id, None)
            if to_del:
                self._rebuild_bm25()
            if save and to_del:
                self._save()
            return len(to_del)

    def clear_seed(self) -> int:
        """只清种子语料，**不动用户上传的内容**。

        为什么单独开一个方法：`POST /api/rag/reindex` 的语义是"重建内置知识库"，
        而它此前调用的是 `clear()` —— 后者会把 chroma collection 整块删掉，
        用户上传的资料随之全部消失，而接口返回的是"重建成功"。
        这类"操作成功但数据没了"的事故，只能靠把语义写进方法名来防。
        """
        with self._lock:
            ids = [d for d, doc in self.documents.items()
                   if is_seed_metadata(doc.get("metadata"))]
            for d in ids:
                self.delete_document(d, save=False)
            if ids:
                self._rebuild_bm25()
                self._save()
            return len(ids)

    def clear(self) -> None:
        with self._lock:
            self.chunks.clear()
            self.documents.clear()
            if self._ensure_chroma() and self._collection is not None:
                try:
                    self._chroma.delete_collection(name=COLLECTION_NAME)
                except Exception:  # noqa: BLE001
                    pass
                self._collection = self._chroma.get_or_create_collection(
                    name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
                )
            self._rebuild_bm25()
            self._save()

    # ------------------------------------------------------------------
    # 检索
    # ------------------------------------------------------------------
    def _vector_search(self, query: str, top_k: int) -> List[tuple]:
        """返回 [(chunk_id, cosine_score)]。"""
        emb = get_embedding()
        if not (emb.available or getattr(emb, "_ensure", None)):
            return []
        try:
            qv = emb.encode_query(query)
        except Exception as e:  # noqa: BLE001
            log.warning("查询向量化失败: %s", e)
            return []
        if not self._ensure_chroma() or self._collection is None:
            return []
        try:
            n = self._collection.count()
            if n == 0:
                return []
            res = self._collection.query(
                query_embeddings=[qv.tolist()],
                n_results=min(top_k, n),
                include=["distances"],
            )
            ids = (res.get("ids") or [[]])[0]
            dists = (res.get("distances") or [[]])[0]
            # Chroma cosine distance = 1 - cosine_similarity
            return [(i, 1.0 - float(d)) for i, d in zip(ids, dists)]
        except Exception as e:  # noqa: BLE001
            log.warning("向量检索失败: %s", e)
            return []

    @staticmethod
    def _rrf(rank_lists: Sequence[Sequence[tuple]], k: int = RRF_K) -> Dict[str, float]:
        """Reciprocal Rank Fusion。rank_lists 每项为 [(id, raw_score), ...]。"""
        fused: Dict[str, float] = {}
        for lst in rank_lists:
            for rank, (cid, _score) in enumerate(lst, 1):
                fused[cid] = fused.get(cid, 0.0) + 1.0 / (k + rank)
        return fused

    def retrieve(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        *,
        min_vector: float = DEFAULT_MIN_VECTOR,
        min_rerank: float = DEFAULT_MIN_RERANK,
        min_bm25: float = DEFAULT_MIN_BM25,
        candidates: int = DEFAULT_CANDIDATES,
        enable_rerank: bool = True,
        filters: Optional[Dict[str, Any]] = None,
    ) -> RetrievalResult:
        started = time.time()
        span = Span(kind="tool", name="rag.retrieve", meta={"query": query[:80]})
        degrade: List[str] = []

        if not query or not query.strip():
            return RetrievalResult(query=query, refused=True,
                                   refuse_reason="查询为空")

        # ---- 1. 双通道召回 -------------------------------------------------
        vec_hits = self._vector_search(query, candidates)
        bm = self._bm25 or BM25()
        bm_hits = bm.search(query, top_k=candidates)

        vec_map = dict(vec_hits)
        bm_map = dict(bm_hits)

        if not vec_hits:
            degrade.append("向量通道不可用（降级为关键词检索）")
        if not bm_hits:
            degrade.append("关键词通道无命中")

        # ---- 2. RRF 融合 ---------------------------------------------------
        fused = self._rrf([vec_hits, bm_hits])
        if not fused:
            res = RetrievalResult(
                query=query, refused=True,
                refuse_reason="知识库中未检索到任何相关内容",
                degraded=True, degrade_reasons=degrade or ["知识库为空"],
                channels={"vector": len(vec_hits), "bm25": len(bm_hits)},
                elapsed_ms=(time.time() - started) * 1000,
            )
            span.finish("ok", error=None)
            metrics.record(span)
            return res

        # 归一化 BM25 分（无上界 → [0,1]，仅用于展示与阈值参考）
        bm_max = max(bm_map.values()) if bm_map else 0.0

        ordered_ids = sorted(fused.items(), key=lambda x: x[1], reverse=True)[:candidates]
        cand_ids = [cid for cid, _ in ordered_ids]

        hits: List[RetrievalHit] = []
        for cid in cand_ids:
            rec = self.chunks.get(cid)
            if not rec:
                continue  # 索引与侧车不一致时跳过，避免 KeyError
            if filters:
                md = {**rec.get("metadata", {}), "source": rec.get("source", "")}
                if not all(md.get(fk) == fv for fk, fv in filters.items()):
                    continue
            vs = float(vec_map.get(cid, 0.0))
            bs = float(bm_map.get(cid, 0.0))
            bsn = (bs / bm_max) if bm_max > 0 else 0.0
            hits.append(
                RetrievalHit(
                    chunk_id=cid,
                    text=rec.get("text", ""),
                    raw_text=rec.get("raw_text", ""),
                    score=float(fused[cid]),
                    vector_score=vs,
                    bm25_score=bsn,
                    bm25_raw=bs,
                    source=rec.get("source", ""),
                    heading_path=rec.get("heading_path", ""),
                    chunk_index=int(rec.get("chunk_index", 0)),
                    metadata=rec.get("metadata", {}),
                )
            )

        # ---- 3. 重排序 -----------------------------------------------------
        rerank_backend = "none"
        if enable_rerank and hits:
            # 必须传 h.text（**带标题路径前缀**），不能传 raw_text。
            # 向量索引用的就是带标题的文本；若给 rerank 看去掉标题的原文，
            # 两个环节看到的内容不一致，rerank 会丢掉"这一节讲的是什么"的关键线索。
            # 实测这一处不一致直接导致可答题「Python中如何定义函数」被误拒。
            backend, scores = get_reranker().rerank(
                query, [h.text for h in hits]
            )
            rerank_backend = backend
            if scores:
                for h, s in zip(hits, scores):
                    # s 可能为 None（该候选未参与重排，见 rerank.py）
                    h.rerank_score = None if s is None else float(s)
                # 排序：**已重排的在前（按 rerank 分降序），未重排的在后（保持 RRF 顺序）**。
                # 不能直接按 `rerank_score or 0.0` 排 —— 那会把未重排候选的
                # None 当成 0，使它们混进已重排区间，顺序变得不可预期。
                hits.sort(key=lambda h: (h.rerank_score is None,
                                         -(h.rerank_score or 0.0)))
                for h in hits:
                    if h.rerank_score is not None:
                        h.score = max(h.score, h.rerank_score)
            elif backend == "none":
                degrade.append("重排序不可用（使用融合排序）")

        # ---- 4. 阈值判定（在截断为 top_k 之前，对全部候选判定）-------------
        # 优先级：rerank 分 > 向量余弦 > BM25 原始分。三者都是**绝对分**，
        # 不随候选集变化，才可能设出稳定的阈值。
        #
        # 关键：**必须对全部候选取各通道最优值，而不是只看排序第一名**。
        # 踩过的坑：RRF 融合后的第一名可能是 BM25 独有的候选
        # （向量通道没召回它 → vector_score=0）。若只看第一名，
        # 就会在正确答案其实排在第 2、3 位时误判"检索不到"而拒答。
        # 实测这个 bug 让可答题的误拒率达到 6.7%。
        refused = False
        reason = ""
        best_rerank: Optional[float] = None
        best_vector = 0.0
        best_bm25raw = 0.0
        if not hits:
            refused = True
            reason = "知识库中未检索到任何相关内容"
        else:
            best_rerank = max(
                (h.rerank_score for h in hits if h.rerank_score is not None),
                default=None,
            )
            best_vector = max((h.vector_score for h in hits), default=0.0)
            best_bm25raw = max((h.bm25_raw for h in hits), default=0.0)

            if best_rerank is not None:
                passed = best_rerank >= min_rerank
                detail = f"rerank 分 {best_rerank:.3f} < {min_rerank}"
            elif vec_hits:
                passed = best_vector >= min_vector
                detail = f"向量相似度 {best_vector:.3f} < {min_vector}"
            else:
                passed = best_bm25raw >= min_bm25
                detail = f"关键词分 {best_bm25raw:.2f} < {min_bm25}"
            if not passed:
                refused = True
                reason = f"知识库中未找到与「{query[:30]}」足够相关的内容（{detail}）"

        hits = hits[:top_k]

        res = RetrievalResult(
            query=query,
            hits=[] if refused else hits,
            refused=refused,
            refuse_reason=reason,
            degraded=bool(degrade),
            degrade_reasons=degrade,
            rerank_backend=rerank_backend,
            channels={"vector": len(vec_hits), "bm25": len(bm_hits)},
            elapsed_ms=(time.time() - started) * 1000,
            # 诊断信息：拒答时也保留，否则事后无法判断是阈值太严还是召回就错了
            best_vector=best_vector,
            best_bm25_raw=best_bm25raw,
            best_rerank=best_rerank,
        )
        span.finish("ok")
        metrics.record(span)
        return res

    # ------------------------------------------------------------------
    # 管理
    # ------------------------------------------------------------------
    def stats(self) -> Dict[str, Any]:
        emb_status = embed_status()
        vec_ready = False
        if self._ensure_chroma() and self._collection is not None:
            try:
                self._collection.count()
                vec_ready = True
            except Exception:  # noqa: BLE001
                vec_ready = False
        return {
            "documents": len(self.documents),
            "chunks": len(self.chunks),
            "bm25_terms": (self._bm25.size if self._bm25 else 0),
            "tokenizer": backend_name(),
            "embedding": emb_status,
            "vector_store_ready": vec_ready,
            "vector_store_error": self._chroma_error,
            "rerank": {
                "preferred": "local:" + RERANK_MODEL_ID.split("/")[-1],
                "local_ready": get_reranker().local_available,
                "fallback": "dashscope_api(qwen3-rerank > gte-rerank-v2)",
            },
            "index_dir": str(self.index_dir),
        }

    def list_documents(self) -> List[Dict[str, Any]]:
        return sorted(
            self.documents.values(), key=lambda d: d.get("indexed_at", 0), reverse=True
        )


# ---------------------------------------------------------------------------
# 单例
# ---------------------------------------------------------------------------

_retriever: Optional[HybridRetriever] = None
_retriever_lock = threading.Lock()


def get_retriever() -> HybridRetriever:
    global _retriever
    if _retriever is None:
        with _retriever_lock:
            if _retriever is None:
                _retriever = HybridRetriever()
    return _retriever
