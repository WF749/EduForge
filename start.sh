#!/bin/bash

echo ""
echo "================================================"
echo "  EduForge · 教铸"
echo "  本地化多模态备课智能体工作台 / Local-first Multimodal Lesson-Prep Agent"
echo "================================================"
echo ""
echo "[提示] 所有依赖将安装在项目目录下的 .venv 文件夹中"
echo "       不会占用系统额外空间"
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 设置 uv 使用本地缓存
export UV_CACHE_DIR="$SCRIPT_DIR/.uv_cache"
export UV_PROJECT_ENVIRONMENT="$SCRIPT_DIR/.venv"

# 检查 uv 是否安装
if ! command -v uv &> /dev/null; then
    echo "[错误] 未检测到 uv！"
    echo ""
    echo "正在安装 uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    if [ $? -ne 0 ]; then
        echo "[错误] uv 安装失败，请手动安装"
        echo "安装地址: https://astral.sh/uv"
        echo ""
        exit 1
    fi
    # 重新加载环境
    export PATH="$HOME/.local/bin:$PATH"
fi

echo "[1/6] 检查 Python 环境..."
uv python install 3.12 --quiet
echo ""

echo "[2/6] 创建本地虚拟环境..."
uv venv --seed --python 3.12
echo ""

echo "[3/6] 安装后端依赖 (使用清华镜像源)..."
uv sync
echo ""

echo "[4/6] 检查 Node.js 和 npm..."
if ! command -v node &> /dev/null; then
    echo "[错误] 未检测到 Node.js！请先安装 Node.js 16+"
    echo "下载地址: https://nodejs.org/"
    echo ""
    exit 1
fi
echo ""

echo "[5/6] 安装前端依赖..."
cd "$SCRIPT_DIR/frontend"
npm install
cd "$SCRIPT_DIR"
echo ""

echo "[6/6] 启动服务..."
echo ""
echo "================================================"
echo "  正在启动服务，请稍候..."
echo "================================================"
echo ""
echo "[提示]"
echo "  - 后端服务: http://localhost:8005"
echo "  - 前端服务: http://localhost:5173"
echo "  - Python 环境: $SCRIPT_DIR/.venv"
echo "  - 缓存目录: $SCRIPT_DIR/.uv_cache"
echo ""

# 启动后端（后台运行）
cd "$SCRIPT_DIR/backend"
"$SCRIPT_DIR/.venv/bin/uvicorn" app.main:app --host 0.0.0.0 --port 8005 --reload &
BACKEND_PID=$!
cd "$SCRIPT_DIR"

# 等待后端启动
sleep 3

# 启动前端
cd "$SCRIPT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!
cd "$SCRIPT_DIR"

echo ""
echo "================================================"
echo "  服务启动完成！"
echo "================================================"
echo ""
echo "请在浏览器打开: http://localhost:5173"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 等待用户中断
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT
wait
