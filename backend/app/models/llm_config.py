"""LLM配置数据库模型"""
from sqlalchemy import Column, Integer, String, Text, Boolean, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pathlib import Path

# 数据库路径
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "llm_config.db"

# 创建基类
Base = declarative_base()

# 创建引擎
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)

# 创建会话
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class LLMConfig(Base):
    """LLM配置表"""
    __tablename__ = "llm_config"
    
    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(50), nullable=False, unique=True)  # 提供商名称
    api_key_encrypted = Column(Text, nullable=True)  # 加密后的API Key
    model = Column(String(100), nullable=True)  # 模型名称
    temperature = Column(Float, default=0.7)  # 温度参数
    base_url = Column(String(255), nullable=True)  # 基础URL
    is_active = Column(Boolean, default=False)  # 是否为当前激活的配置

# 创建表
def create_tables():
    """创建数据库表"""
    Base.metadata.create_all(bind=engine)

# 获取数据库会话
def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 初始化默认配置
def init_default_config():
    """初始化默认配置"""
    db = SessionLocal()
    try:
        # 检查是否已有配置
        existing_configs = db.query(LLMConfig).count()
        if existing_configs == 0:
            # 创建默认配置
            default_providers = ["dashscope", "openai", "deepseek", "local", "demo"]
            for provider in default_providers:
                config = LLMConfig(
                    provider=provider,
                    api_key_encrypted=None,
                    model=None,
                    temperature=0.7,
                    base_url=None,
                    is_active=(provider == "demo")  # 默认激活演示模式
                )
                db.add(config)
            db.commit()
    finally:
        db.close()

if __name__ == "__main__":
    # 创建表
    create_tables()
    # 初始化默认配置
    init_default_config()
    print("数据库初始化完成！")
