"""向量编码层 —— 本地 bge-small-zh-v1.5（512 维）。

设计原则：**降级必须诚实**。

模型加载失败时，不会用一个"看起来能跑但其实没语义"的假 embedding 顶替
（那会让检索质量静默劣化，且极难排查）。而是明确标记 unavailable，
由 retriever 切换为 BM25 单通道，并在每次结果里声明 `degraded` 原因。

查询侧指令前缀
--------------
bge 系列在「短查询 → 长文档」场景下，官方要求给查询加指令前缀：
    "为这个句子生成表示以用于检索相关文章："
文档侧不加。实测在中文教学语料上，加前缀的召回明显更稳。
"""

from __future__ import annotations

import glob
import os
import threading
from pathlib import Path
from typing import List, Optional, Sequence

import numpy as np

from ..core.logging_setup import get_logger

log = get_logger("rag.embedding")

MODEL_ID = "BAAI/bge-small-zh-v1.5"
QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："
EXPECTED_DIM = 512

# 模型缓存根目录：backend/models_cache
# 注意 parents 层级：本文件在 backend/app/rag/ → parents[2] 才是 backend/
_CACHE_ROOT = Path(__file__).resolve().parents[2] / "models_cache"


def _local_snapshot(model_id: str = MODEL_ID) -> Optional[Path]:
    """在本地缓存里找已下载好的模型快照目录。

    HF 缓存布局：models_cache/models--BAAI--bge-small-zh-v1.5/snapshots/<hash>/
    """
    slug = "models--" + model_id.replace("/", "--")
    pattern = str(_CACHE_ROOT / slug / "snapshots" / "*")
    cands = [Path(p) for p in glob.glob(pattern)]
    for c in sorted(cands):
        if (c / "config.json").exists() and (
            (c / "model.safetensors").exists() or (c / "pytorch_model.bin").exists()
        ):
            return c
    return None


class EmbeddingBackend:
    """所有 embedding 后端的统一接口。"""

    name: str = "none"
    dim: int = 0
    available: bool = False
    reason: str = ""

    def encode_documents(self, texts: Sequence[str]) -> np.ndarray:
        raise NotImplementedError

    def encode_query(self, query: str) -> np.ndarray:
        raise NotImplementedError


class BGEEmbedding(EmbeddingBackend):
    """本地 bge-small-zh-v1.5。首次调用时懒加载（模型约 95MB，加载 ~1s）。"""

    name = "bge-small-zh-v1.5"

    def __init__(self, model_path: Optional[str] = None) -> None:
        self._model = None
        self._lock = threading.Lock()
        self._path = model_path or os.getenv("EDUFORGE_EMBED_MODEL") or ""
        self._load_error: Optional[str] = None
        self.dim = EXPECTED_DIM

    # -- 内部 ---------------------------------------------------------------
    def _resolve(self) -> Optional[str]:
        if self._path:
            return self._path
        snap = _local_snapshot()
        if snap:
            return str(snap)
        return MODEL_ID  # 交给 sentence-transformers 自行解析/下载

    def _ensure(self) -> bool:
        if self._model is not None:
            return True
        if self._load_error:
            return False
        with self._lock:
            if self._model is not None:
                return True
            try:
                # 延迟导入：没有装 sentence-transformers 时不应在 import 阶段炸掉
                from sentence_transformers import SentenceTransformer

                # 国内网络下 huggingface.co 经常不可达，统一走镜像
                os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
                path = self._resolve()
                log.info("加载 embedding 模型: %s", path)
                self._model = SentenceTransformer(path)
                # sentence-transformers v5 起方法改名为 get_embedding_dimension，
                # 两种都试以兼容新旧版本（旧版无新方法会回退）
                getter = getattr(self._model, "get_embedding_dimension", None) \
                    or self._model.get_sentence_embedding_dimension
                self.dim = int(getter())
                self.available = True
                return True
            except Exception as e:  # noqa: BLE001 - 任何失败都降级，不阻断服务
                self._load_error = f"{type(e).__name__}: {e}"
                self.available = False
                self.reason = f"embedding 模型加载失败：{self._load_error}"
                log.warning("embedding 模型不可用，将降级为关键词检索：%s", self._load_error)
                return False

    # -- 接口 ---------------------------------------------------------------
    def encode_documents(self, texts: Sequence[str]) -> np.ndarray:
        if not self._ensure():
            raise RuntimeError(self.reason or "embedding 不可用")
        texts = [t if t.strip() else " " for t in texts]
        vecs = self._model.encode(
            list(texts), batch_size=32, normalize_embeddings=True, show_progress_bar=False
        )
        return np.asarray(vecs, dtype=np.float32)

    def encode_query(self, query: str) -> np.ndarray:
        if not self._ensure():
            raise RuntimeError(self.reason or "embedding 不可用")
        v = self._model.encode(
            [QUERY_INSTRUCTION + query], normalize_embeddings=True, show_progress_bar=False
        )
        return np.asarray(v, dtype=np.float32)[0]


class UnavailableEmbedding(EmbeddingBackend):
    """明确的"不可用"占位。

    存在的意义是让调用方拿到一个可用对象，但 `available=False` 是显式的，
    避免到处写 `if model is None`。
    """

    name = "unavailable"

    def __init__(self, reason: str) -> None:
        self.available = False
        self.reason = reason

    def encode_documents(self, texts: Sequence[str]) -> np.ndarray:
        raise RuntimeError(self.reason)

    def encode_query(self, query: str) -> np.ndarray:
        raise RuntimeError(self.reason)


# ---------------------------------------------------------------------------
# 单例
# ---------------------------------------------------------------------------

_backend: Optional[EmbeddingBackend] = None
_backend_lock = threading.Lock()


def get_embedding(force_reload: bool = False) -> EmbeddingBackend:
    """获取全局 embedding 后端（进程内只加载一次模型）。"""
    global _backend
    if _backend is not None and not force_reload:
        return _backend
    with _backend_lock:
        if _backend is not None and not force_reload:
            return _backend

        if os.getenv("EDUFORGE_DISABLE_EMBEDDING", "").strip() in ("1", "true", "True"):
            _backend = UnavailableEmbedding("已通过环境变量禁用向量检索")
            return _backend

        try:
            backend = BGEEmbedding()
            # 立即触发一次加载，让 available / reason 在首次检索前就确定下来
            ok = backend._ensure()  # noqa: SLF001 - 同模块内主动初始化
            _backend = backend if ok else UnavailableEmbedding(backend.reason)
        except Exception as e:  # noqa: BLE001
            _backend = UnavailableEmbedding(f"embedding 初始化失败：{type(e).__name__}: {e}")
        return _backend


def embed_status() -> dict:
    """给 /api/rag/status 用的可读状态。"""
    b = get_embedding()
    return {
        "backend": b.name,
        "available": bool(b.available),
        "dim": int(getattr(b, "dim", 0) or 0),
        "reason": b.reason or "",
        "local_model_path": str(_local_snapshot() or ""),
        "query_instruction": QUERY_INSTRUCTION if b.available else "",
    }


def embed_texts(texts: List[str]) -> np.ndarray:
    return get_embedding().encode_documents(texts)
