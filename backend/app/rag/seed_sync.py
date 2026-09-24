"""种子知识库的增量同步：新增 / 变更 / 删除，按文件内容 hash 判定。

为什么需要它
------------
启动时的播种原先只看"文档 id 在不在索引里"，于是：

  * 修改了 `knowledge_base/` 里的一篇，重启后**索引里还是旧内容** ——
    教师改了知识库却查不到新内容，只会以为"系统坏了"；
  * 删掉了某篇文件，重启后**索引里依然留着它**，继续被检索出来 ——
    等于把已经废弃的内容继续喂给模型。

这两种都不会报错、不会告警，是典型的静默失效。现在改成按 sha256 比对：

  * 文件在、索引无        → 新增
  * 文件在、hash 不同     → 重建（add_document 本身幂等）
  * 文件没了、索引还在    → 删除

hash 写进 metadata，因此也能被 `/api/rag/status` 之类的接口读出来做诊断。

关于 origin
-----------
种子与上传的区分只认 `origin` 字段（见 retriever.ORIGIN_SEED / ORIGIN_UPLOAD）。
这里产出的 metadata 是**唯一**的构造入口，避免各处自己拼字段导致口径漂移。
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from .frontmatter import split_frontmatter
from .retriever import ORIGIN_SEED, is_seed_metadata

__all__ = [
    "content_hash", "seed_metadata", "seed_body", "seed_files",
    "rebuild_seed_index", "sync_seed_index", "maybe_upload_metadata",
]


def content_hash(text: str) -> str:
    """内容指纹。用 sha256 的前 16 位足够，且不受编码差异影响（先 encode utf-8）。"""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def seed_metadata(filename: str, content: str, **extra: Any) -> Dict[str, Any]:
    """种子文档的统一 metadata。

    字段含义见 retriever 里 origin 的说明：origin 管"能删什么"，
    source 与 filename 管展示与溯源，content_hash 管增量同步。

    `content` 传**原始全文**（含 frontmatter）：
      * hash 用全文 —— 改了元数据也算变，索引会重建；
      * 文档头部的 frontmatter 会被解析成 stage / subject / grades 等字段，
        供 `/api/rag/search` 的 filters 使用（例如只看初中物理）。
    """
    front, _body = split_frontmatter(content)
    meta: Dict[str, Any] = {
        "origin": ORIGIN_SEED,
        "source": ORIGIN_SEED,
        "filename": filename,
        "content_hash": content_hash(content),
    }
    meta.update(front)
    meta.update(extra)
    return meta


def seed_body(content: str) -> str:
    """去掉 frontmatter 后的正文 —— 索引只吃正文。

    不剥掉的话，`stage: 初中` 这类行会被切进 chunk：既污染检索，
    溯源时也会显示成一段莫名其妙的正文。
    """
    return split_frontmatter(content)[1]


def seed_files(kb_dir) -> List[Path]:
    """知识库目录下的全部种子文件（只认 md / txt，与 reindex 保持一致）。"""
    kb = Path(kb_dir)
    if not kb.exists():
        return []
    return sorted(list(kb.glob("*.md")) + list(kb.glob("*.txt")))


def rebuild_seed_index(retriever, kb_dir) -> Dict[str, Any]:
    """全量重建种子索引（先清种子，再逐篇加入）。

    这是**唯一**的重建入口：`POST /api/rag/reindex` 与 `scripts/rag_eval.py`
    都用它。此前评测脚本自己写了一份，用的是 `clear()`（会把用户上传一起删掉）
    和旧的 metadata 写法 —— 于是"评测跑过的索引"和"线上实际用的索引"是两套，
    改了一处另一处不动，评测结果也就说明不了线上行为。
    """
    removed = retriever.clear_seed()
    added: List[str] = []
    errors: List[Dict[str, str]] = []
    for path in seed_files(kb_dir):
        try:
            raw = path.read_text(encoding="utf-8")
            retriever.add_document(path.stem, seed_body(raw), seed_metadata(path.name, raw))
            added.append(path.stem)
        except Exception as e:  # noqa: BLE001
            errors.append({"document_id": path.stem, "error": str(e)})
    return {
        "added": added,
        "removed": removed,
        "errors": errors,
        "documents": len(retriever.documents),
        "chunks": len(retriever.chunks),
    }


def sync_seed_index(retriever, kb_dir, *, verbose: bool = False) -> Dict[str, Any]:
    """把索引里的种子部分同步到与磁盘一致。返回本次做了什么，供启动日志使用。

    **只动种子文档**：用户上传的内容（origin=upload）一律不碰 ——
    即便某个上传文档的 id 恰好与知识库里的文件名相同，也不会被误删。
    """
    files = {f.stem: f for f in seed_files(kb_dir)}

    indexed_seed = {
        doc_id: doc
        for doc_id, doc in retriever.documents.items()
        if is_seed_metadata((doc or {}).get("metadata"))
    }

    removed: List[str] = []
    added: List[str] = []
    updated: List[str] = []
    errors: List[Dict[str, str]] = []

    # 1) 文件已删 → 移除索引
    for doc_id in list(indexed_seed):
        if doc_id not in files:
            try:
                retriever.delete_document(doc_id)
                removed.append(doc_id)
            except Exception as e:  # noqa: BLE001
                errors.append({"document_id": doc_id, "error": str(e)})

    # 2) 文件在 → 按 hash 决定是否重建
    for stem, path in files.items():
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            errors.append({"document_id": stem, "error": str(e)})
            continue
        if not content.strip():
            continue

        digest = content_hash(content)
        existing = indexed_seed.get(stem)
        old_hash = ((existing or {}).get("metadata") or {}).get("content_hash")
        if existing and old_hash == digest:
            continue  # 内容没变，不重算向量（省时间也省额度）

        try:
            retriever.add_document(
                stem, seed_body(content), seed_metadata(path.name, content)
            )
            (updated if existing else added).append(stem)
        except Exception as e:  # noqa: BLE001
            errors.append({"document_id": stem, "error": str(e)})

    result = {
        "added": added,
        "updated": updated,
        "removed": removed,
        "unchanged": len(files) - len(added) - len(updated),
        "errors": errors,
        "documents": len(retriever.documents),
        "chunks": len(retriever.chunks),
    }
    if verbose:
        print(f"知识库种子同步: 新增 {len(added)} / 更新 {len(updated)} / "
              f"删除 {len(removed)} / 未变 {result['unchanged']}，"
              f"索引共 {result['documents']} 篇 {result['chunks']} 片段")
        for e in errors:
            print(f"  索引失败 {e.get('document_id')}: {e.get('error')}")
    return result


def maybe_upload_metadata(filename: str, file_id: str = "") -> Dict[str, Any]:
    """上传文档的 metadata（与 seed_metadata 成对出现，口径一致）。"""
    return {
        "origin": "upload",
        "source": filename,
        "filename": filename,
        "file_id": file_id,
    }
