"""
知识库存储：默认使用本地 JSON 持久化（快、无额外模型下载）。
仅当环境变量 USE_CHROMA=1 时才尝试 Chroma（适合已装好向量依赖的环境）。

统一入口（2026-09-02）
----------------------
本项目此前存在**两套互不相通的知识库**：
  1. 本模块 —— 供对话页与文件上传使用，检索靠字符重合打分，中文效果差；
  2. `services/rag_service` —— 供课件/教案生成使用，Chroma + 英文 embedding。

同一个文件在"对话"里能搜到、在"生成课件"里搜不到，是真实的用户困扰。
现在二者统一到 `app/rag/retriever.py` 的混合检索器：

  * JSON 仍然是**上传内容的持久化真源**（列表、删除、版本管理都依赖它）；
  * 写入时**同步**建混合索引（向量 + BM25）；
  * 查询走混合检索，失败时自动退回本模块的字符重合打分。

所有对 `app.rag` 的导入都是**函数内惰性导入**：本模块被启动时最早加载的
代码路径引用，同步加载 embedding 模型会拖慢启动，且模型缺失会连带整个后端起不来。
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from .core.logging_setup import get_logger
from .paths import CHROMA_DIR, DATA_DIR

log = get_logger("knowledge_store")

_lock = threading.Lock()
KB_PATH = DATA_DIR / "knowledge_base_store.json"
_collection = None  # chroma lazy
_docs_cache: Optional[Dict[str, Any]] = None


def _use_chroma() -> bool:
    return os.getenv("USE_CHROMA", "").strip().lower() in ("1", "true", "yes", "on")


def _rag():
    """惰性获取统一检索器；不可用时返回 None，由调用方走本地兜底。"""
    try:
        from .rag.retriever import get_retriever
        return get_retriever()
    except Exception as e:  # noqa: BLE001
        log.debug("统一检索器不可用，走本地兜底: %s", e)
        return None


def _rag_enabled() -> bool:
    return os.getenv("EDUFORGE_DISABLE_UNIFIED_RAG", "").strip().lower() not in (
        "1", "true", "yes", "on"
    )


def _load_disk() -> Dict[str, Any]:
    global _docs_cache
    with _lock:
        if _docs_cache is not None:
            return _docs_cache
        if KB_PATH.exists():
            try:
                raw = KB_PATH.read_text(encoding="utf-8")
                _docs_cache = json.loads(raw)
                if "documents" not in _docs_cache:
                    _docs_cache = {"documents": {}}
            except Exception:
                _docs_cache = {"documents": {}}
        else:
            _docs_cache = {"documents": {}}
        return _docs_cache


def _save_disk() -> None:
    global _docs_cache
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = KB_PATH.with_suffix(".tmp")
    data = _docs_cache or {"documents": {}}
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(KB_PATH)


def _get_chroma():
    global _collection
    if not _use_chroma():
        return False
    if _collection is not None:
        return _collection
    try:
        import chromadb

        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        _collection = client.get_or_create_collection(
            name="teaching_kb",
            metadata={"hnsw:space": "cosine"},
        )
    except Exception:
        _collection = False
    return _collection


def reset_fallback() -> None:
    global _docs_cache
    with _lock:
        _docs_cache = {"documents": {}}
        _save_disk()


def add_chunks(
    doc_id: str,
    filename: str,
    chunks: List[str],
    meta: Optional[Dict] = None,
    chunk_size: Optional[int] = None,
) -> None:
    """写入主存储（JSON）；可选同步到 Chroma。"""
    if not chunks:
        chunks = ["(空内容)"]

    store = _load_disk()
    with _lock:
        store.setdefault("documents", {})[doc_id] = {
            "filename": filename,
            "chunks": chunks,
            "meta": meta or {},
        }
        _docs_cache = store
        try:
            _save_disk()
        except Exception:
            pass

    if _use_chroma():
        col = _get_chroma()
        if col and col is not False:
            try:
                ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
                col.add(
                    ids=ids,
                    documents=chunks,
                    metadatas=[{"doc_id": doc_id, "filename": filename} for _ in chunks],
                )
            except Exception:
                pass

    # 同步到统一检索器。失败只记日志——上传流程不能因为索引问题而中断，
    # 用户仍可通过本地兜底检索到内容。
    if _rag_enabled():
        try:
            r = _rag()
            if r is not None:
                r.add_document(
                    doc_id,
                    "\n".join(chunks),
                    metadata={"filename": filename, **(meta or {}), "origin": "upload"},
                    chunk_size=chunk_size or 320,
                )
        except Exception as e:  # noqa: BLE001
            log.warning("同步到统一检索索引失败(%s): %s", doc_id, e)


def delete_document(doc_id: str) -> bool:
    store = _load_disk()
    existed = False
    with _lock:
        docs = store.get("documents") or {}
        if doc_id in docs:
            existed = True
            del docs[doc_id]
            _docs_cache = store
            try:
                _save_disk()
            except Exception:
                pass

    if _use_chroma():
        col = _get_chroma()
        if col and col is not False:
            try:
                data = col.get(where={"doc_id": doc_id})
                if data and data.get("ids"):
                    col.delete(ids=data["ids"])
            except Exception:
                pass

    if _rag_enabled():
        try:
            r = _rag()
            if r is not None:
                r.delete_document(doc_id)
        except Exception as e:  # noqa: BLE001
            log.warning("从统一检索索引删除失败(%s): %s", doc_id, e)
    return existed


def clear_all() -> None:
    reset_fallback()
    global _collection
    if _use_chroma():
        try:
            import chromadb

            client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            client.delete_collection("teaching_kb")
        except Exception:
            pass
        _collection = None

    # 注意：不清空统一检索器中的**种子知识库**。
    # clear_all 的语义是"清空用户上传的知识"，而种子文档由 /api/rag/reindex 管理，
    # 一并清掉会让用户莫名其妙失去内置资料。
    if _rag_enabled():
        try:
            r = _rag()
            if r is not None:
                for d in list(r.documents.keys()):
                    if (r.documents[d].get("metadata") or {}).get("origin") == "upload":
                        r.delete_document(d)
        except Exception as e:  # noqa: BLE001
            log.warning("清空统一检索索引中的上传文档失败: %s", e)


def stats() -> Dict[str, Any]:
    store = _load_disk()
    docs = store.get("documents") or {}
    total_chunks = sum(len(d.get("chunks") or []) for d in docs.values())
    return {
        "total_documents": len(docs),
        "total_chunks": total_chunks,
        "status": "ready" if docs else "empty",
    }


def list_documents(limit: int = 100) -> List[Dict[str, Any]]:
    store = _load_disk()
    out: List[Dict[str, Any]] = []
    for did, d in list((store.get("documents") or {}).items())[:limit]:
        chunks = d.get("chunks") or []
        out.append(
            {
                "id": did,
                "count": len(chunks),
                "metadata": {"filename": d.get("filename", did)},
            }
        )
    return out


def _score_chunk(query: str, chunk: str) -> float:
    q = (query or "").strip()
    if not q:
        return 0.0
    ch = chunk or ""
    if q in ch:
        return 0.95
    # 字符级重合（适合中文无分词）
    qs = set(q)
    cs = set(ch)
    if not qs:
        return 0.0
    overlap = len(qs & cs) / len(qs)
    # 连续子串加分
    bonus = 0.0
    for n in (4, 3, 2):
        if len(q) >= n:
            for i in range(len(q) - n + 1):
                if q[i : i + n] in ch:
                    bonus = max(bonus, 0.15 * n)
    return min(1.0, overlap * 0.7 + bonus)


def query_kb(q: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """统一检索入口。

    优先走混合检索（向量 + BM25 + 重排序 + 拒答阈值）；
    不可用时退回本模块的字符重合打分，保证功能不中断。

    返回结构保持向后兼容：调用方读取的 `content` / `score` 字段不变，
    额外附带 `source` / `heading_path` 用于引用溯源。
    """
    # ---- 1. 统一混合检索 --------------------------------------------------
    if _rag_enabled():
        try:
            r = _rag()
            if r is not None:
                res = r.retrieve(q, top_k=top_k)
                if res.refused:
                    # 拒答：不返回任何上下文，避免模型拿着无关内容编造
                    return []
                return [
                    {
                        "content": h.raw_text,
                        "score": round(h.score, 4),
                        "source": h.source,
                        "heading_path": h.heading_path,
                        "vector_score": round(h.vector_score, 4),
                        "rerank_score": (None if h.rerank_score is None
                                         else round(h.rerank_score, 4)),
                    }
                    for h in res.hits
                ]
        except Exception as e:  # noqa: BLE001
            log.warning("统一检索失败，回退本地检索: %s", e)

    # ---- 2. 本地兜底（原逻辑）-------------------------------------------
    store = _load_disk()
    results: List[Dict[str, Any]] = []
    for did, d in (store.get("documents") or {}).items():
        for ch in d.get("chunks") or []:
            sc = _score_chunk(q, ch)
            if sc > 0.05:
                results.append({
                    "content": ch[:2000],
                    "score": sc,
                    "doc_id": did,
                    "source": d.get("filename") or did,
                })
    results.sort(key=lambda x: x["score"], reverse=True)
    out = [
        {"content": r["content"], "score": r["score"], "source": r.get("source", "")}
        for r in results[:top_k]
    ]

    if out or not _use_chroma():
        return out

    col = _get_chroma()
    if col and col is not False:
        try:
            res = col.query(query_texts=[q], n_results=min(top_k, 20))
            docs = (res.get("documents") or [[]])[0]
            dists = (res.get("distances") or [[]])[0] if res.get("distances") else []
            alt = []
            for i, doc in enumerate(docs):
                score = 1.0 - float(dists[i]) if i < len(dists) else 0.5
                alt.append({"content": doc, "score": max(0.0, min(1.0, score))})
            return alt[:top_k]
        except Exception:
            pass
    return out


def chunk_text(text: str, size: int = 900) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []
    # 略增大块减少条数，加快写入
    chunks = []
    i = 0
    while i < len(text):
        chunks.append(text[i : i + size])
        i += size
    return chunks


def stable_doc_id(name: str) -> str:
    return hashlib.sha256(name.encode("utf-8")).hexdigest()[:24]


def doc_id_for_upload(file_id: str) -> str:
    """每个上传文件唯一 ID，避免同名覆盖。"""
    return f"file_{file_id}"
