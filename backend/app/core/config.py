"""应用配置（与主项目 paths 对齐：知识库在仓库根目录 knowledge_base/）"""
import os
from pathlib import Path

# backend/ 目录
_BACKEND = Path(__file__).resolve().parent.parent.parent
_PROJECT_ROOT = _BACKEND.parent

# 上传目录（与 app.paths 一致）
UPLOAD_DIR = _BACKEND / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# 知识库目录：仓库根 knowledge_base（与种子 Markdown 一致）
KNOWLEDGE_BASE_DIR = _PROJECT_ROOT / "knowledge_base"
KNOWLEDGE_BASE_DIR.mkdir(exist_ok=True)

# 向量数据库目录
CHROMA_PERSIST_DIRECTORY = _BACKEND / "data" / "chromadb"
CHROMA_PERSIST_DIRECTORY.mkdir(parents=True, exist_ok=True)


class Settings:
    """应用配置类"""
    APP_NAME = "EduForge"
    APP_VERSION = "1.0.0"
    DEBUG = True

    HOST = "0.0.0.0"
    PORT = 8005

    CORS_ORIGINS = ["*"]

    MAX_FILE_SIZE = 100 * 1024 * 1024
    ALLOWED_EXTENSIONS = {
        "pdf", "doc", "docx", "ppt", "pptx", "txt", "md",
        "jpg", "jpeg", "png", "gif", "bmp",
        "mp4", "avi", "mov", "wmv",
        "mp3", "wav", "flac", "aac",
    }

    # 不再默认 demo：未配置真实模型时系统应明确报错，而非静默返回编造内容
    DEFAULT_LLM_PROVIDER = "openai"
    DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    LOCAL_MODEL_URL = os.getenv("LOCAL_MODEL_URL", "http://localhost:8001/v1")

    # 中文优化的本地 embedding，离线可用（企业级 RAG 的基础）
    EMBEDDING_MODEL = "bge-small-zh-v1.5"

    CHROMA_PERSIST_DIRECTORY = str(CHROMA_PERSIST_DIRECTORY)
    CHROMA_COLLECTION_NAME = "knowledge_base"

    CHUNK_SIZE = 500
    CHUNK_OVERLAP = 50
    TOP_K = 5
    TEMPERATURE = 0.7


class KnowledgeConfig:
    CHUNK_SIZE = 500
    CHUNK_OVERLAP = 50
    TOP_K = 5
    TEMPERATURE = 0.7


settings = Settings()
knowledge_config = KnowledgeConfig()

# 兼容旧代码引用 BASE_DIR
BASE_DIR = _BACKEND
