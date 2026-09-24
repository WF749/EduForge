"""RAG 接口：检索、文档管理、索引状态。

对外只暴露"检索"与"管理"两类能力，所有阈值与降级细节都在
`app/rag/retriever.py` 内部处理，接口层不重复实现业务逻辑。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

from ..core.errors import AppError
from ..core.logging_setup import get_logger
from ..rag.retriever import get_retriever

log = get_logger("api.rag")
router = APIRouter()


@router.get("/status")
def status():
    """索引与两通道的可用状态。

    前端可据此提示用户"当前仅有关键词检索"等降级情况，
    避免用户以为系统坏了。
    """
    try:
        return {"success": True, **get_retriever().stats()}
    except Exception as e:  # noqa: BLE001
        log.exception("获取 RAG 状态失败")
        return {"success": False, "message": f"获取状态失败：{e}"}


@router.post("/search")
def search(body: Dict[str, Any] = Body(...)):
    """混合检索。

    返回片段均带 source / heading_path，可直接用于引用溯源。
    `refused=true` 表示判定为"知识库里没有"，此时 hits 为空，
    调用方应当明确告知用户，而不是让模型自由发挥。
    """
    query = (body.get("query") or "").strip()
    if not query:
        return JSONResponse(status_code=422, content={
            "success": False, "code": "E4001", "message": "缺少 query 参数"})

    try:
        result = get_retriever().retrieve(
            query,
            top_k=int(body.get("top_k") or 5),
            enable_rerank=bool(body.get("rerank", True)),
            filters=body.get("filters"),
        )
    except AppError as e:
        return JSONResponse(status_code=e.status, content=e.to_dict())
    except Exception as e:  # noqa: BLE001
        log.exception("RAG 检索失败")
        return JSONResponse(status_code=500, content={
            "success": False, "code": "E9002", "message": f"检索失败：{e}"})

    out = result.to_dict()
    out["context"] = result.context_block()
    out["success"] = True
    return out


@router.get("/documents")
def list_documents():
    try:
        r = get_retriever()
        return {"success": True, "count": len(r.documents),
                "documents": r.list_documents()}
    except Exception as e:  # noqa: BLE001
        return {"success": False, "message": f"获取文档列表失败：{e}"}


@router.post("/documents")
def add_document(body: Dict[str, Any] = Body(...)):
    """索引一篇文档。相同 document_id 会先删旧再重建（幂等）。"""
    doc_id = (body.get("document_id") or "").strip()
    content = body.get("content") or ""
    if not doc_id or not content.strip():
        return JSONResponse(status_code=422, content={
            "success": False, "code": "E4002",
            "message": "缺少 document_id 或 content"})

    try:
        res = get_retriever().add_document(
            doc_id, content, metadata=body.get("metadata") or {}
        )
        return {"success": True, **res}
    except Exception as e:  # noqa: BLE001
        log.exception("索引文档失败")
        return JSONResponse(status_code=500, content={
            "success": False, "code": "E9003", "message": f"索引失败：{e}"})


@router.delete("/documents/{document_id}")
def delete_document(document_id: str):
    try:
        n = get_retriever().delete_document(document_id)
        return {"success": True, "document_id": document_id, "removed_chunks": n}
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=500, content={
            "success": False, "code": "E9004", "message": f"删除失败：{e}"})


@router.post("/reindex")
def reindex():
    """用仓库根 knowledge_base/ 下的 md/txt 重建**种子索引**。

    只重建 origin=seed 的部分，**用户上传的资料不受影响**。
    此前这里调用的是 `clear()` —— 那会连 chroma collection 一起删掉，
    教师上传的课件与资料在一次"重建内置知识库"里被全部抹掉，
    而接口返回 success。现在语义写死在 `clear_seed()` 里。
    """
    from ..core.config import KNOWLEDGE_BASE_DIR
    from pathlib import Path
    from ..rag.retriever import ORIGIN_SEED
    from ..rag.seed_sync import seed_metadata

    kb = Path(KNOWLEDGE_BASE_DIR)
    if not kb.exists():
        return JSONResponse(status_code=404, content={
            "success": False, "code": "E4004", "message": f"知识库目录不存在: {kb}"})

    r = get_retriever()
    removed = r.clear_seed()
    indexed: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    for f in sorted(list(kb.glob("*.md")) + list(kb.glob("*.txt"))):
        try:
            st = r.add_document(f.stem, f.read_text(encoding="utf-8"),
                                seed_metadata(f.name, f.read_text(encoding="utf-8")))
            indexed.append({"document_id": f.stem, **st})
        except Exception as e:  # noqa: BLE001
            errors.append({"file": f.name, "error": str(e)})

    return {
        "success": not errors,
        "origin": ORIGIN_SEED,
        "removed": removed,
        "documents": len(indexed),
        "chunks": sum(i.get("chunks", 0) for i in indexed),
        "errors": errors,
        "items": indexed,
    }
