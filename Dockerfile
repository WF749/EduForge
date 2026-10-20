# EduForge — 单容器部署（前端静态页 + 后端 API 同源，最适合免费托管平台）
# 构建阶段 1：编译前端
FROM node:18-bullseye AS frontend-build
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --registry=https://registry.npmmirror.com
COPY frontend/ ./
RUN npm run build

# 运行阶段：后端（uv 管理依赖）
FROM python:3.11-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

# 系统依赖（PDF 解析 / 图像处理）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential poppler-utils libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv（依赖与运行环境管理）
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 后端依赖（pyproject.toml + uv.lock）
COPY pyproject.toml uv.lock* ./
COPY backend/ ./backend/

# ⚠️ 为什么这里强制用官方 PyPI：
# uv.lock 里的包地址指向清华镜像（对国内使用者友好），但构建镜像的 CI runner
# 在美国，跨太平洋拉 500MB 的 torch 会反复超时（实测 torch / cudnn / triton
# 三个包各超时一次，整次构建失败）。
# 这里只覆盖"从哪下"，不改任何版本（pyproject 里绝大多数是 == 固定版本）。
ENV UV_INDEX_URL=https://pypi.org/simple
ENV UV_HTTP_TIMEOUT=600
ENV UV_CONCURRENT_DOWNLOADS=4

# 去掉 --frozen：允许按新的索引重新解析；版本仍由 pyproject 固定
RUN uv venv --python 3.11 && uv sync --no-dev
ENV PATH="/app/.venv/bin:$PATH"

# 前端构建产物放入 backend 静态托管目录（main.py 自动托管）
COPY --from=frontend-build /src/frontend/dist ./frontend/dist

WORKDIR /app/backend
ENV HOST=0.0.0.0
ENV PORT=8005
EXPOSE 8005

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8005"]
