"""企业级 RAG 全链路。

为什么重写，而不是继续用 services/rag_service.py
------------------------------------------------
原实现有三个会直接伤害用户的问题：

1. **英文模型检索中文**：使用 `all-MiniLM-L6-v2`，中文语义向量质量很差，
   "牛顿第二定律" 与 "F=ma" 这类同义表述基本召回不到。
2. **只有向量检索**：没有关键词通道。教学资料里大量专有名词
   （"一元二次方程""阅读理解主旨大意题"）是精确术语，
   纯向量容易漏召，必须 BM25 补齐。
3. **无阈值、无溯源、无评测**：检索不到相关内容时也硬塞给模型，
   导致模型编造；出了问题也没有量化手段定位到底是哪一环退化了。

本包按"每一环都可度量、都可降级、都可解释"的原则重建。

分层
----
  embeddings  向量编码（本地 bge-small-zh-v1.5，失败降级为 BM25-only）
  chunker     中文结构感知分块（保留标题路径，便于溯源与引用）
  bm25        纯 Python BM25（中文分词优先 jieba，降级为字符二元组）
  rerank      重排序（本地 CrossEncoder / 百炼 rerank API / 不重排）
  retriever   混合检索 + RRF 融合 + 拒答阈值 + 引用溯源（对外主入口）
  evalset     评测集与指标（Recall@k / MRR / 拒答准确率）
"""

from .retriever import HybridRetriever, RetrievalHit, RetrievalResult, get_retriever

__all__ = ["HybridRetriever", "RetrievalHit", "RetrievalResult", "get_retriever"]
