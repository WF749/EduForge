@echo off
chcp 65001 >nul
title EduForge - 启动脚本

echo.
echo ================================================
echo   EduForge · 教铸
echo   本地化多模态备课智能体工作台
echo ================================================
echo.
echo [提示] 所有依赖将安装在项目目录下的 .venv 文件夹中
echo        不会占用C盘额外空间
echo.

setlocal

set "PROJECT_DIR=%~dp0"
set "UV_CACHE_DIR=%PROJECT_DIR%.uv_cache"
set "VENV_DIR=%PROJECT_DIR%.venv"

if not exist "%UV_CACHE_DIR%" mkdir "%UV_CACHE_DIR%"

uv --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 uv！
    echo.
    echo 正在安装 uv...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    if errorlevel 1 (
        echo [错误] uv 安装失败，请手动安装
        echo 安装地址: https://astral.sh/uv
        echo.
        pause
        exit /b 1
    )
    call "%USERPROFILE%\.cargo\env.bat" 2>nul
)

if exist "%VENV_DIR%\Scripts\python.exe" (
    echo [1/4] 环境已存在，跳过安装...
    goto :start_server
)

echo [1/5] 检查 Python 环境...
uv python install 3.12 --quiet
echo.

echo [2/5] 创建本地虚拟环境...
uv venv --seed --python 3.12
echo.

echo [3/5] 安装后端依赖 (使用清华镜像源)...
uv pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple ^
    fastapi==0.109.0 ^
    uvicorn[standard]==0.27.0 ^
    python-multipart==0.0.6 ^
    dashscope==1.14.1 ^
    "openai>=1.60.0,<2" ^
    httpx>=0.27.0 ^
    PyPDF2==3.0.1 ^
    pdfplumber>=0.10.0 ^
    python-docx==0.8.11 ^
    python-pptx==0.6.23 ^
    olefile>=0.46 ^
    Pillow==9.5.0 ^
    pytesseract==0.3.10 ^
    moviepy==1.0.3 ^
    pydub==0.25.1 ^
    "chromadb>=0.5.0" ^
    "numpy<2.0.0" ^
    sentence-transformers ^
    python-dotenv==1.0.0 ^
    requests==2.31.0 ^
    matplotlib>=3.7.0
echo.

:start_server
echo [2/4] 检查 Node.js 和 npm...
node --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Node.js！请先安装 Node.js 16+
    echo 下载地址: https://nodejs.org/
    echo.
    pause
    exit /b 1
)
echo.

if not exist "%PROJECT_DIR%frontend\node_modules" (
    echo [3/4] 安装前端依赖...
    cd frontend
    call npm install
    cd ..
) else (
    echo [3/4] 前端依赖已存在，跳过安装...
)
echo.

echo [4/4] 启动服务...
echo.
echo ================================================
echo   正在启动服务，请稍候...
echo ================================================
echo.
echo [提示]
echo   - 后端服务: http://localhost:8005
echo   - 前端服务: http://localhost:5173
echo   - Python 环境: %VENV_DIR%
echo   - 缓存目录: %UV_CACHE_DIR%
echo   - 按 Ctrl+C 可停止服务
echo.

start "后端服务" cmd /k "cd /d %PROJECT_DIR%backend && ..\.venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8005"

timeout /t 3 >nul

start "前端服务" cmd /k "cd /d %PROJECT_DIR%frontend && npm run dev"

echo ================================================
echo   服务启动完成！
echo ================================================
echo.
echo 请在浏览器打开: http://localhost:5173
echo.
pause
endlocal
