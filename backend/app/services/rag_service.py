"""增强版RAG服务"""
from typing import List, Dict, Optional
import os
import re
import glob
import hashlib
import shutil
import gc
import time
import sys
from datetime import datetime
from pathlib import Path

from ..core.config import CHROMA_PERSIST_DIRECTORY

COLLECTION_NAME = "teaching_knowledge"


def _is_chroma_index_error(exc: BaseException) -> bool:
    """Chroma 持久化目录损坏或 HNSW 索引异常时常见关键字"""
    msg = str(exc).lower()
    needles = (
        "hnsw",
        "compaction",
        "segment",
        "loading hnsw",
        "index",
        "corrupt",
        "sqlite",
        "readonly",
        "compactor",
        "backfill",
    )
    return any(n in msg for n in needles)

# ── HuggingFace 镜像配置（解决国内无法访问 huggingface.co 导致模型下载超时） ──
# 如果未设置 HF_ENDPOINT 且 huggingface.co 可能不通，自动使用镜像
if not os.environ.get("HF_ENDPOINT"):
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
if not os.environ.get("SENTENCE_TRANSFORMERS_HOME"):
    # 模型缓存到项目本地目录，避免重复下载
    _model_cache = os.path.join(os.path.dirname(__file__), "..", "..", "models_cache")
    os.makedirs(_model_cache, exist_ok=True)
    os.environ["SENTENCE_TRANSFORMERS_HOME"] = _model_cache

# 安全导入依赖（缺失时不会导致整个后端崩溃）
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False
    print("警告: chromadb 未安装，知识库功能将不可用。请运行: pip install chromadb")

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False
    print("警告: sentence-transformers 未安装，向量检索将不可用。请运行: pip install sentence-transformers")

class RAGService:
    """增强版RAG服务类"""
    
    def __init__(self):
        """初始化RAG服务"""
        self.client = None
        self.collection = None
        self.embedding_model = None
        self.document_ids = set()
        
        if HAS_CHROMADB:
            try:
                self._init_chroma()
            except Exception as e:
                print(f"ChromaDB 初始化失败: {e}")
                if _is_chroma_index_error(e):
                    print("检测到向量索引/持久化异常，尝试重建 data/chromadb …")
                    if self._nuclear_rebuild_chroma():
                        try:
                            self._init_chroma()
                        except Exception as e2:
                            print(f"重建后仍无法初始化 ChromaDB: {e2}")
                else:
                    print(f"ChromaDB 初始化失败（非索引类错误）: {e}")

    def _persist_path(self) -> str:
        return str(CHROMA_PERSIST_DIRECTORY)

    def _init_chroma(self):
        persist_dir = self._persist_path()
        os.makedirs(persist_dir, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(name=COLLECTION_NAME)
        try:
            self._restore_document_ids()
        except Exception as e:
            if not _is_chroma_index_error(e):
                raise
            print(f"向量索引损坏，将重建持久化目录: {e}")
            if not self._nuclear_rebuild_chroma():
                raise RuntimeError(
                    "无法重建向量库目录（可能被其他进程占用 chroma.sqlite3）。"
                    "请关闭本服务外的 Python/进程后重启，或手动删除 backend/data/chromadb 再启动。"
                ) from e
            self.client = chromadb.PersistentClient(
                path=self._persist_path(),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self.collection = self.client.get_or_create_collection(name=COLLECTION_NAME)
            self.document_ids.clear()

    def storage_key_for(self, document_id: str) -> str:
        """与用户可见文件名对应的稳定存储键（避免特殊字符与超长 ID 引发底层问题）"""
        h = hashlib.sha256(document_id.encode("utf-8")).hexdigest()[:40]
        return f"doc_{h}"

    def _recreate_collection_only(self) -> bool:
        """仅删除并重建 collection（保留 persist 目录下其他文件）"""
        if self.client is None:
            return False
        try:
            try:
                self.client.delete_collection(name=COLLECTION_NAME)
            except Exception:
                pass
            self.collection = self.client.get_or_create_collection(name=COLLECTION_NAME)
            self.document_ids.clear()
            return True
        except Exception as e:
            print(f"重建 collection 失败: {e}")
            return False

    def _release_chroma_handles(self):
        """释放 PersistentClient 占用的文件句柄（Windows 上否则无法移动/删除目录）"""
        self.collection = None
        try:
            if self.client is not None:
                del self.client
        except Exception:
            pass
        self.client = None
        gc.collect()
        # Chroma/SQLite 析构释放锁需要短暂间隔
        time.sleep(0.4 if sys.platform == "win32" else 0.1)

    def _nuclear_rebuild_chroma(self) -> bool:
        """将损坏的 chromadb 目录移走并新建空目录（会丢失已有向量索引）"""
        persist = self._persist_path()
        try:
            self.document_ids.clear()
            self._release_chroma_handles()
            if os.path.isdir(persist):
                backup = f"{persist}_corrupt_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                last_err = None
                for attempt in range(5):
                    try:
                        shutil.move(persist, backup)
                        print(f"已备份损坏的向量库目录到: {backup}")
                        last_err = None
                        break
                    except OSError as e:
                        last_err = e
                        self._release_chroma_handles()
                        time.sleep(0.5 * (attempt + 1))
                if last_err is not None:
                    print(f"重建向量库目录失败（文件仍被占用，请关闭其他占用 Chroma 的进程后重试）: {last_err}")
                    return False
            os.makedirs(persist, exist_ok=True)
            return True
        except Exception as e:
            print(f"重建向量库目录失败: {e}")
            return False

    def repair_vector_store(self) -> bool:
        """供 API 调用：强制清空并重建持久化向量库（解决 HNSW / compaction 类错误）"""
        if not HAS_CHROMADB:
            return False
        ok = self._nuclear_rebuild_chroma()
        if not ok:
            return False
        try:
            self._init_chroma()
            return self.collection is not None
        except Exception as e:
            print(f"repair_vector_store 初始化失败: {e}")
            return False
    
    def _restore_document_ids(self):
        """从 ChromaDB 恢复已有的 document_ids（用户可见名存于 original_filename）"""
        if self.collection is None:
            return
        try:
            count = self.collection.count()
            if count == 0:
                return
            results = self.collection.get(include=["metadatas"], limit=count)
            if results and results.get("metadatas"):
                for meta in results["metadatas"]:
                    if not meta:
                        continue
                    orig = meta.get("original_filename")
                    if orig:
                        self.document_ids.add(orig)
                        continue
                    did = meta.get("document_id")
                    # 旧数据：document_id 直接为文件名等非 hash 形式
                    if did and not (
                        isinstance(did, str) and did.startswith("doc_") and len(did) == 44
                    ):
                        self.document_ids.add(did)
            if self.document_ids:
                print(f"从ChromaDB恢复了 {len(self.document_ids)} 个文档记录")
        except Exception as e:
            if _is_chroma_index_error(e):
                raise
            print(f"恢复document_ids失败: {e}")
    
    def _load_embedding_model(self):
        """加载嵌入模型（优先使用本地缓存，支持镜像下载）"""
        if self.embedding_model is None:
            if not HAS_SENTENCE_TRANSFORMERS:
                self.embedding_model = False
                return
            try:
                print("正在加载嵌入模型 all-MiniLM-L6-v2 ...")
                self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
                print("嵌入模型加载成功")
            except Exception as e:
                print(f"加载嵌入模型失败: {str(e)}")
                print("提示: 如无法下载模型，请手动下载 all-MiniLM-L6-v2 到 backend/models_cache/ 目录")
                self.embedding_model = False
    
    def initialize(self):
        """初始化RAG服务"""
        os.makedirs(self._persist_path(), exist_ok=True)
    
    def add_document(self, document_id: str, content: str, metadata: Dict = None):
        """添加文档到知识库"""
        if self.collection is None:
            raise Exception("知识库服务未就绪，请检查 chromadb 是否已安装")
        
        self._load_embedding_model()
        
        if self.embedding_model is False:
            raise Exception("嵌入模型未就绪，请检查 sentence-transformers 是否已安装")
        
        # 分割文档为chunk
        chunks = self._split_document(content)
        
        # 生成嵌入向量
        embeddings = self.embedding_model.encode(chunks)
        
        storage_key = self.storage_key_for(document_id)
        # 为每个 chunk 生成唯一 ID（与用户文件名解耦，避免特殊字符与路径问题）
        chunk_ids = [f"{storage_key}_{i}" for i in range(len(chunks))]
        
        # 准备元数据：向量库内 document_id 为稳定 hash；original_filename 供展示与删除
        metadatas = []
        for i, chunk in enumerate(chunks):
            chunk_metadata = dict(metadata) if metadata else {}
            chunk_metadata["document_id"] = storage_key
            chunk_metadata["original_filename"] = document_id
            chunk_metadata["chunk_index"] = i
            metadatas.append(chunk_metadata)
        
        last_err: Optional[Exception] = None
        for attempt in range(3):
            try:
                self.collection.add(
                    ids=chunk_ids,
                    documents=chunks,
                    embeddings=embeddings.tolist(),
                    metadatas=metadatas,
                )
                self.document_ids.add(document_id)
                return
            except Exception as e:
                last_err = e
                if not _is_chroma_index_error(e):
                    raise
                if attempt == 0:
                    print(f"Chroma 写入失败（索引异常），尝试重建 collection: {e}")
                    self._recreate_collection_only()
                elif attempt == 1:
                    print(f"重建 collection 后仍失败，尝试重建持久化目录: {e}")
                    if self._nuclear_rebuild_chroma():
                        self._init_chroma()
                else:
                    raise
        if last_err:
            raise last_err
    
    def query(self, query: str, top_k: int = 5) -> List[Dict]:
        """查询知识库"""
        if self.collection is None:
            return []
        
        self._load_embedding_model()
        
        if self.embedding_model is False:
            return []
        
        # 生成查询向量
        query_embedding = self.embedding_model.encode([query])[0]
        
        # 在ChromaDB中查询
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )
        
        # 处理结果
        formatted_results = []
        for i, (document, metadata, distance) in enumerate(zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        )):
            # 计算相似度分数 (1 - 距离，因为距离越小越相似)
            score = 1.0 - distance
            
            formatted_results.append({
                "content": document,
                "score": score,
                "metadata": metadata
            })
        
        return formatted_results
    
    def delete_document(self, document_id: str):
        """删除文档"""
        if self.collection is None:
            return
        sk = self.storage_key_for(document_id)
        try:
            self.collection.delete(where={"document_id": sk})
        except Exception:
            pass
        try:
            # 兼容旧数据：metadata.document_id 曾直接为原始文件名
            self.collection.delete(where={"document_id": document_id})
        except Exception:
            pass
        if document_id in self.document_ids:
            self.document_ids.remove(document_id)
    
    def clear(self):
        """清空知识库"""
        if self.client is None:
            return
        self.client.delete_collection(name=COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(name=COLLECTION_NAME)
        
        # 清空文档ID集合
        self.document_ids.clear()
    
    def get_stats(self) -> Dict:
        """获取知识库统计信息"""
        chunk_count = 0
        if self.collection is not None:
            try:
                chunk_count = self.collection.count()
            except Exception:
                pass
        status = "ready" if (self.collection is not None and HAS_SENTENCE_TRANSFORMERS) else "not_ready"
        return {
            "total_documents": len(self.document_ids),
            "total_chunks": chunk_count,
            "status": status
        }
    
    def auto_index_seed_data(self, knowledge_dir: str):
        """自动索引种子知识库数据"""
        knowledge_path = Path(knowledge_dir)
        if not knowledge_path.exists():
            print(f"知识库目录不存在: {knowledge_dir}")
            return
        
        # 扫描所有md和txt文件
        indexed_count = 0
        for ext in ['*.md', '*.txt']:
            for filepath in knowledge_path.glob(ext):
                document_id = filepath.stem
                
                # 跳过已索引的文档
                if document_id in self.document_ids:
                    continue
                
                try:
                    content = filepath.read_text(encoding='utf-8')
                    if not content.strip():
                        continue
                    
                    # 从文件名提取元数据
                    metadata = {
                        "source": "seed",
                        "filename": filepath.name,
                        "file_type": filepath.suffix[1:]
                    }
                    parts = document_id.split('_')
                    if len(parts) >= 3:
                        metadata["subject"] = parts[1]
                        metadata["topic"] = '_'.join(parts[2:])
                    elif len(parts) >= 2:
                        metadata["subject"] = parts[1]
                    
                    self.add_document(document_id=document_id, content=content, metadata=metadata)
                    indexed_count += 1
                    print(f"  已索引: {filepath.name}")
                except Exception as e:
                    print(f"  索引失败 {filepath.name}: {e}")
        
        if indexed_count > 0:
            print(f"种子知识库索引完成: 新增{indexed_count}个文档")
        else:
            print(f"种子知识库: 无新文档需要索引 (已有{len(self.document_ids)}个文档)")
    
    def get_context_for_generation(self, topic: str, audience: str = "", key_points: List[str] = None, top_k: int = 5) -> str:
        """检索知识库上下文，用于注入课件/教案生成 prompt。

        优先走统一检索器（`app/rag/retriever`）：中文 embedding + 混合检索 +
        重排序 + 拒答阈值，并且和对话页共用同一份索引（此前两套知识库互不相通）。
        不可用时退回本类的旧实现，保证生成流程不中断。
        """
        query_parts = [topic]
        if audience:
            query_parts.append(audience)
        if key_points:
            query_parts.extend(key_points)
        composite_query = " ".join(p for p in query_parts if p)

        try:
            from ..rag.retriever import get_retriever

            res = get_retriever().retrieve(composite_query, top_k=top_k)
            if res.refused or not res.hits:
                return ""
            return res.context_block()
        except Exception as e:  # noqa: BLE001
            print(f"统一检索不可用，回退旧 RAG: {e}")

        results = self.query(composite_query, top_k=top_k)
        filtered = [r for r in results if r.get("score", 0) > 0.3]

        if not filtered:
            return ""

        context_lines = ["【知识库参考资料】"]
        for i, r in enumerate(filtered[:3], 1):
            content = r["content"][:300]
            source = r.get("metadata", {}).get("filename", "未知来源")
            context_lines.append(f"{i}. {content}\n   (来源: {source})")

        return "\n".join(context_lines)
    
    def _is_chinese_text(self, content: str) -> bool:
        """检测文本是否主要为中文"""
        if not content:
            return False
        non_space = re.sub(r'\s', '', content)
        if not non_space:
            return False
        cjk_count = sum(1 for c in non_space if '\u4e00' <= c <= '\u9fff')
        return cjk_count / len(non_space) > 0.3
    
    def _split_document(self, content: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[str]:
        """分割文档为chunk（支持中文）"""
        if not content or not content.strip():
            return [content] if content else []
        
        if self._is_chinese_text(content):
            return self._split_chinese(content, chunk_size=300, chunk_overlap=50)
        else:
            return self._split_english(content, chunk_size, chunk_overlap)
    
    def _split_chinese(self, content: str, chunk_size: int = 300, chunk_overlap: int = 50) -> List[str]:
        """中文文本分块：按句子分割，再贪心合并"""
        sentences = re.split(r'(?<=[。！？；\n])', content)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return [content]
        
        chunks = []
        current_chunk = ""
        overlap_sentences = []
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= chunk_size:
                current_chunk += sentence
                overlap_sentences.append(sentence)
                if len(overlap_sentences) > 2:
                    overlap_sentences.pop(0)
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                if chunk_overlap > 0 and overlap_sentences:
                    current_chunk = "".join(overlap_sentences) + sentence
                else:
                    current_chunk = sentence
                overlap_sentences = [sentence]
        
        if current_chunk and current_chunk not in chunks:
            chunks.append(current_chunk)
        
        return chunks if chunks else [content]
    
    def _split_english(self, content: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[str]:
        """英文文本分块：按空格分词"""
        chunks = []
        words = content.split()
        
        if not words:
            return [content]
        
        for i in range(0, len(words), chunk_size - chunk_overlap):
            chunk = " ".join(words[i:i + chunk_size])
            chunks.append(chunk)
        
        return chunks if chunks else [content]

# 实例化RAG服务
rag_service = RAGService()