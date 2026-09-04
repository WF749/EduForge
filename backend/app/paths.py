"""Resolved filesystem paths (backend cwd is project/backend when started by startup.ps1)."""
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent  # 仓库根目录；部分路径解析仍需要

DATA_DIR = BACKEND_DIR / "data"
# 与 docker-compose、.gitignore 一致：运行时目录放在 backend/ 下
UPLOAD_DIR = BACKEND_DIR / "uploads"
GENERATED_CW = BACKEND_DIR / "generated_courseware"
GENERATED_ANIM = BACKEND_DIR / "generated_animations"
GENERATED_GAMES = BACKEND_DIR / "generated_games"
GENERATED_LP = BACKEND_DIR / "generated_lesson_plans"
CHROMA_DIR = BACKEND_DIR / "chroma_data"

CONFIG_JSON = DATA_DIR / "runtime_config.json"
CHAT_STORE = DATA_DIR / "chat_history.json"
FILE_REGISTRY = DATA_DIR / "uploaded_files.json"


def ensure_dirs() -> None:
    for p in (
        DATA_DIR,
        UPLOAD_DIR,
        GENERATED_CW,
        GENERATED_ANIM,
        GENERATED_GAMES,
        GENERATED_LP,
        CHROMA_DIR,
    ):
        p.mkdir(parents=True, exist_ok=True)
