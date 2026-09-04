"""重排序（Rerank）—— 混合检索后、喂给模型前的精排环节。

为什么需要
----------
向量与 BM25 都是**无监督**打分：向量看语义距离，BM25 看词面重叠。
它们共同的短板是缺乏"这段到底能不能回答这个问题"的判断。
例如查询"求根公式的推导步骤"，向量可能召回"求根公式的应用"，
词面高度重合但答非所问。Rerank 用交叉编码（query 与 doc 一起进模型）
做有监督判断，是 RAG 里性价比最高的一步。

三级降级，每一级都如实上报
--------------------------
  local          本地 bge-reranker-base（默认首选：无网络依赖、数据不出校）
  dashscope_api  百炼 qwen3-rerank（本地模型缺失时的云端兜底）
  none           不重排，保留 RRF 融合顺序

为什么默认走本地
----------------
本项目定位是"本地 / 内网优先，数据不出校"。重排序会把**用户查询 + 知识库原文**
一起送到模型，若走云端 API 就等于把校内资料外传，与定位相悖。
因此本地 cross-encoder 是首选，云端 API 仅作兜底。
此外本地模型不受账户余额影响 —— 实测百炼账户欠费时 API 直接 400，
把核心检索链路挂在"账户余额"上是不可接受的。

**绝不用"假装重排"**：若某级失败，返回 scores=None，由 retriever
保持原顺序并在结果中标注 rerank_backend="none"。
"""

from __future__ import annotations

import glob
import math
import os
from pathlib import Path
from typing import List, Optional, Sequence

from ..core.logging_setup import get_logger

log = get_logger("rag.rerank")

RERANK_TIMEOUT = 20.0

MODEL_ID = "BAAI/bge-reranker-base"

# cross-encoder 的开销 = O(候选数 × token²)，是整条链路唯一的重计算环节。
# 实测（16 核 CPU，bge-reranker-base，候选片段平均 98 字）：
#     20 条 → ~2100ms   8 条 → ~870ms   不重排 → ~13ms
# 我们最终只返回 top-5，把 20 条全送进 cross-encoder 是纯粹的浪费，
# 因此只重排融合分最高的前 8 条，其余保持 RRF 顺序排在后面。
RERANK_CANDIDATES = 8

# 单条文本送进 cross-encoder 前的字符上限。
# 既是延迟护栏（防止超长片段把 p95 拖爆），也符合 cross-encoder
# 对长文本判别力下降的已知特性。
RERANK_MAX_CHARS = 400

# 模型缓存根目录：backend/models_cache
# 本文件在 backend/app/rag/ → parents[2] 才是 backend/
_CACHE_ROOT = Path(__file__).resolve().parents[2] / "models_cache"


def _sigmoid(scores: Sequence[float]) -> List[float]:
    """把 cross-encoder 的 logit 压到 0~1。

    分支写法保证 exp 的自变量恒 <= 0，因此不存在溢出问题。
    """
    out: List[float] = []
    for s in scores:
        x = float(s)
        if x >= 0:
            e = math.exp(-x)          # -x <= 0
            out.append(1.0 / (1.0 + e))
        else:
            e = math.exp(x)           # x < 0
            out.append(e / (1.0 + e))
    return out


def _local_snapshot() -> Optional[Path]:
    """在本地缓存里找已下载好的 bge-reranker-base 快照目录。"""
    slug = "models--" + MODEL_ID.replace("/", "--")
    cands = [Path(p) for p in glob.glob(str(_CACHE_ROOT / slug / "snapshots" / "*"))]
    for c in sorted(cands):
        if (c / "config.json").exists() and (
            (c / "model.safetensors").exists() or (c / "pytorch_model.bin").exists()
        ):
            return c
    return None


class Reranker:
    def __init__(self) -> None:
        self._cross_encoder = None
        self._cross_loaded = False

    # ------------------------------------------------------------------
    # 本地交叉编码器
    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_path() -> str:
        """模型路径优先级：环境变量 > 本地缓存快照 > 空（表示未就绪）。"""
        env = os.getenv("EDUFORGE_RERANK_MODEL", "").strip()
        if env:
            return env
        snap = _local_snapshot()
        return str(snap) if snap else ""

    def _load_cross_encoder(self):
        if self._cross_loaded:
            return self._cross_encoder
        self._cross_loaded = True
        path = self._resolve_path()
        if not path:
            log.info("本地 rerank 模型未就绪，将使用云端兜底 "
                     "（执行 python scripts/fetch_embedding_model.py --model rerank 下载）")
            return None
        try:
            from sentence_transformers import CrossEncoder

            self._cross_encoder = CrossEncoder(path)
            log.info("本地 rerank 模型已加载: %s", path)
        except Exception as e:  # noqa: BLE001
            log.warning("本地 rerank 模型加载失败（跳过）: %s", e)
            self._cross_encoder = None
        return self._cross_encoder

    @property
    def local_available(self) -> bool:
        """本地模型是否已就绪（供健康检查/状态接口上报）。"""
        return bool(self._resolve_path())

    # ------------------------------------------------------------------
    # 百炼 rerank API
    # ------------------------------------------------------------------
    @staticmethod
    def _dashscope_rerank(
        query: str, documents: Sequence[str], api_key: str, model: str = "qwen3-rerank"
    ) -> Optional[List[float]]:
        """调用百炼文本重排序 API。返回每个文档的相关性分数。"""
        import httpx

        url = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
        payload = {
            "model": model,
            "input": {"query": query, "documents": list(documents)},
            "parameters": {"return_documents": False},
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=RERANK_TIMEOUT, verify=False) as client:
                resp = client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                log.warning("百炼 rerank 返回 %s: %s", resp.status_code, resp.text[:200])
                return None
            data = resp.json()
            results = (data.get("output") or {}).get("results") or []
            if len(results) != len(documents):
                return None
            return [float(r.get("relevance_score") or 0.0) for r in results]
        except Exception as e:  # noqa: BLE001
            log.warning("百炼 rerank 调用失败: %s", e)
            return None

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------
    def rerank(
        self, query: str, documents: Sequence[str], api_key: Optional[str] = None
    ) -> tuple:
        """返回 (backend, scores)。scores 为 None 表示未重排。

        backend ∈ {"local:<model>", "dashscope_api:<model>", "none"}
        """
        if not documents:
            return "none", None

        # 1) 本地 cross-encoder（默认首选，见模块 docstring）
        ce = self._load_cross_encoder()
        if ce is not None:
            try:
                # bge-reranker-base 输出未归一化的 logit（约 -12 ~ +12），
                # 与百炼 API 的 0~1 不同尺度；压到 0~1 后阈值只维护一套。
                trimmed = [d[:RERANK_MAX_CHARS] for d in documents[:RERANK_CANDIDATES]]
                scores = _sigmoid(ce.predict([[query, d] for d in trimmed]))
                # 未参与重排的候选记为 None：由调用方保持原顺序排在后面，
                # 且不参与阈值判定。不能用 0 填充 —— 那会污染 max() 的基准。
                scores = list(scores) + [None] * (len(documents) - len(trimmed))
                return "local:" + MODEL_ID.split("/")[-1], scores
            except Exception as e:  # noqa: BLE001
                log.warning("本地 rerank 推理失败: %s", e)

        # 2) 百炼 API（复用用户已配置的 Key）
        key = (api_key or "").strip() or self._dashscope_key()
        if key:
            # 模型顺序是实测选的，不是随便排的：
            #   qwen3-rerank   相关 0.76 / 无关 0.17~0.20，区分度大，分数落在 0~1
            #   gte-rerank-v2  分数被压缩在 0~0.2，区分仍在但绝对跨度小，作为备胎
            for model in ("qwen3-rerank", "gte-rerank-v2"):
                scores = self._dashscope_rerank(query, documents, key, model=model)
                if scores is not None:
                    return f"dashscope_api:{model}", scores

        return "none", None

    @staticmethod
    def _dashscope_key() -> str:
        """从运行时配置读取百炼 Key（不落日志、不外传）。"""
        try:
            from ..persist import load_runtime_config

            cfg = load_runtime_config() or {}
            keys = cfg.get("apiKeys") or {}
            key = (keys.get("dashscope") or "").strip()
            # 仅当当前激活厂商就是 dashscope 时才自动使用，避免越权使用未激活的 Key
            return key if key and cfg.get("provider") == "dashscope" else ""
        except Exception:  # noqa: BLE001
            return ""


_reranker: Optional[Reranker] = None


def get_reranker() -> Reranker:
    global _reranker
    if _reranker is None:
        _reranker = Reranker()
    return _reranker


def rerank(
    query: str, documents: Sequence[str], api_key: Optional[str] = None
) -> tuple:
    return get_reranker().rerank(query, documents, api_key)
