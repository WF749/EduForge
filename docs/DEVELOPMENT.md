# 开发流程

> 面向人和 AI 编码工具。命令均在本仓库实际验证过；Windows 下用 Git Bash 执行。

## 1. 环境

- Python：`>=3.10, <3.13`（`pyproject.toml` 约束），依赖用 **uv + pyproject.toml** 管理，**不要**改回 pip。
- Node：前端 Vite 构建用。
- 一键启动：双击仓库根目录 `启动项目.bat`。

## 2. 启动

```bash
# 后端（端口 8005，同时托管前端生产包）
cd backend && PYTHONPATH=. uv run --project . uvicorn app.main:app --host 127.0.0.1 --port 8005

# 前端开发模式（另开终端，5173）
cd frontend && npm run dev
```

后端起来后访问 <http://127.0.0.1:8005> 即为完整应用（走 `frontend/dist`）。

Docker：`cp .env.example .env` 后 `docker compose up -d --build`，访问 `http://localhost:8005`。

## 3. 测试与验证（全部纯本地、零模型额度）

```bash
# 在项目根目录执行，当前基线 176 项全绿
PYTHONPATH=backend uv run --project backend python scripts/smoke_safety.py             # 数据合规 70
PYTHONPATH=backend uv run --project backend python scripts/smoke_teaching_compliance.py # 教学合规 77
PYTHONPATH=backend uv run --project backend python scripts/smoke_lesson_plan.py         # 教案健壮性 29
```

其他：

```bash
make eval          # 100 条 RAG 评测集（含 rerank）
make eval-quick    # 只跑检索层，零成本可离线
make reindex       # 用 knowledge_base/ 重建 RAG 索引
make fetch-model   # 下载中文 embedding 模型（95MB），离线可用
```

## 4. 前端构建

**禁止直接 `npm run build`**（会清空在用的 `frontend/dist`，详见
[CONSTRAINTS.md §A1](CONSTRAINTS.md#a1-禁止直接-npm-run-build)）。

```bash
cd frontend
npx vite build --outDir .build-new --emptyOutDir    # 构建到临时目录
grep -rl "本次改动的关键字" .build-new/assets/*.js    # 确认新代码已打包
mv dist dist_old && mv .build-new dist               # 重命名替换
# 起后端验证：/ 返回 index.html、/assets/xxx.js 返回 200，确认后分批删除 dist_old
```

> 批量删除有 50 个文件阈值保护，删 `dist_old` 时分批：
> `find dist_old -type f | head -46 | xargs rm -f`（重复至清空）。

## 5. 提交

```bash
git status          # 确认无运行期产物（dist/、logs/、backend/data/、generated_*/、uploads/）
git add -A
git commit -m "类型(范围): 做了什么 + 为什么"
git push            # 远端 origin/main
```

仓库在 GitHub：`WF749/EduForge`（私有）。**不要 force push**。

## 6. 常见故障排查

### 「生成成功但内容全空」

先看 `finish_reason`，**不要靠猜**：

```bash
PYTHONPATH=backend uv run --project backend python scripts/diag_lesson_plan_stage3.py
# 会真实调模型（约 2 分钟）并打印：stop = 正常；length = 输出被 max_tokens 截断
```

截断时检查 `resolve_max_tokens()` 是否仍 ≥ 8192（见 [CONSTRAINTS.md §D1](CONSTRAINTS.md#d1-输出上限不得低于-8192)）。

### 合规规则大量误报

先确认正则是否带 `(?<![一-龥])` 词首锚定，以及非人名标签黑名单是否覆盖
（见 [CONSTRAINTS.md §C3](CONSTRAINTS.md#c3-新增规则必须同步补反例测试)）。

### 端口 8005 被占用

说明上次后端进程未退出。Windows：

```powershell
Get-NetTCPConnection -LocalPort 8005 | Select-Object -ExpandProperty OwningProcess | Stop-Process -Force
```

### git 连不上 GitHub（本机网络特性）

报错 `CRYPT_E_NO_REVOCATION_CHECK (0x80092012)`：本机有本地代理做 TLS 中间人，
而 Windows 查不到证书吊销状态。**两项必须同时配**才生效：

```bash
git config --global http.sslBackend schannel
git config --global http.schannelCheckRevoke false
```

### `gh` 提示未登录，但浏览器里已授权

某些终端（如 WorkBuddy 内置的 bash）没有 `APPDATA` 环境变量，
gh 会回退到空的 `~/.config/gh`，于是明明已授权却显示未登录。补上即可：

```bash
# Windows（Git Bash）
export APPDATA="$USERPROFILE/AppData/Roaming"
```

> 注：文档中**不要写死** `C:\Users\<某用户>\...` 这类本机绝对路径，请用环境变量表示。

## 7. 改动后的自检清单

- [ ] 三条 smoke 全绿
- [ ] 动了生成链路 → 响应里的 `compliance` 字段仍在
- [ ] 动了 `backend/app/safety/` → `smoke_safety.py` 的静态插桩校验通过
- [ ] 动了前端 → dist 已按 §4 重建并验证可访问
- [ ] `git status` 无运行期产物
- [ ] 非显而易见的取舍已写进提交信息或文档
