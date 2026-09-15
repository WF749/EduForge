import os
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import api_routes
from .api import agent as agent_api
from .api import courseware as courseware_api
from .api import lesson_plan as lesson_plan_api
from .api import lesson_tasks as lesson_tasks_api
from .api import ppt as ppt_api
from .api import rag as rag_api
from .api import safety as safety_api
from .api import system as system_api
from .api import teaching_compliance as teaching_compliance_api
from .core.errors import install_exception_handlers
from .core.logging_setup import setup_logging
from .core.middleware import install_middleware
from .core.observability import metrics
from .paths import (
    GENERATED_ANIM,
    GENERATED_CW,
    GENERATED_GAMES,
    GENERATED_LP,
    UPLOAD_DIR,
    ensure_dirs,
)

# ---------------------------------------------------------------------------
# 工程体系初始化：日志 → 异常处理 → 中间件 → 指标落盘
# 顺序有意义：日志先就绪，后续初始化才有地方报错。
# ---------------------------------------------------------------------------
_LOG_DIR = Path(__file__).resolve().parent.parent / "data" / "logs"
setup_logging(level=os.getenv("LOG_LEVEL", "INFO"), log_dir=_LOG_DIR)
metrics.configure(_LOG_DIR)

app = FastAPI(title="EduForge", version="2.0.0")

install_exception_handlers(app)
install_middleware(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


# 业务接口统一在 /api 下，这里补一个同义路径，
# 便于只暴露 /api 前缀的反向代理与健康检查使用。
@app.get("/api/health")
def api_health():
    return {"status": "ok"}


# 课件 / PPT / 教案：完整生成栈（与设置页 runtime_config.json 打通）
app.include_router(courseware_api.router, prefix="/api")
app.include_router(ppt_api.router, prefix="/api")
app.include_router(lesson_plan_api.router, prefix="/api")
# 「一节课」的台账：课程上下文 + 四类产物归属 + 参考资料关联
app.include_router(lesson_tasks_api.router, prefix="/api")

# 新增：系统/可观测性（/api/providers、/api/models/live、/api/metrics）
app.include_router(system_api.router, prefix="/api")
# 新增：企业级 RAG（/api/rag/search、/documents、/reindex、/status）
app.include_router(rag_api.router, prefix="/api/rag")
# 新增：Agent 能力（/api/agent/tools、/plan、/run、/stream）
app.include_router(agent_api.router, prefix="/api/agent")
# 新增：数据合规预检（/api/safety/status、/scan）—— 本地判别，不调用模型
app.include_router(safety_api.router, prefix="/api")
# 新增：教学合规校验器（/api/teaching-compliance/check）—— 离线规则，零额度
app.include_router(teaching_compliance_api.router, prefix="/api")

app.include_router(api_routes.router)


def _rag_seed_background():
    """启动时把 knowledge_base/ 下的种子文档补进统一检索索引。

    只补**尚未索引**的文档，已存在则跳过——否则每次启动都重算一遍向量，
    既慢又白白消耗额度。完整重建请用 `POST /api/rag/reindex`。
    """
    try:
        from .core.config import KNOWLEDGE_BASE_DIR
        from .rag.retriever import get_retriever

        r = get_retriever()
        known = set(r.documents.keys())
        added = 0
        for f in sorted(list(Path(KNOWLEDGE_BASE_DIR).glob("*.md"))
                        + list(Path(KNOWLEDGE_BASE_DIR).glob("*.txt"))):
            if f.stem in known:
                continue
            try:
                r.add_document(f.stem, f.read_text(encoding="utf-8"),
                               {"filename": f.name, "source": "seed"})
                added += 1
            except Exception as e:  # noqa: BLE001
                print(f"  索引 {f.name} 失败: {e}")
        print(f"知识库种子索引: 新增 {added} 篇，索引内共 {len(r.documents)} 篇"
              f" / {len(r.chunks)} 片段")
    except Exception as e:  # noqa: BLE001
        print(f"知识库后台索引: {e}")


threading.Thread(target=_rag_seed_background, daemon=True, name="rag-seed-index").start()

ensure_dirs()
for mount_name, directory in (
    ("uploads", UPLOAD_DIR),
    ("generated_courseware", GENERATED_CW),
    ("generated_animations", GENERATED_ANIM),
    ("generated_games", GENERATED_GAMES),
    ("generated_lesson_plans", GENERATED_LP),
):
    directory.mkdir(parents=True, exist_ok=True)
    app.mount(f"/{mount_name}", StaticFiles(directory=str(directory)), name=mount_name)


# ---------------------------------------------------------------------------
# 生产环境前端托管（仅当 frontend/dist 已构建时生效；本地 Vite 开发不受影响）
# 单容器部署时，前端静态页与 API 同源，避免跨域与 baseURL 配置问题。
# ---------------------------------------------------------------------------
_FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    # API 路径未命中时交由 FastAPI 返回 JSON 404，而非前端页面
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")
    dist = _FRONTEND_DIST
    candidate = dist / full_path
    if dist.exists() and candidate.is_file():
        return FileResponse(str(candidate))
    index = dist / "index.html"
    if index.exists():
        return FileResponse(str(index))
    raise HTTPException(status_code=404, detail="frontend not built")
