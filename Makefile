# EduForge 常用工程任务
#
# Windows 用户：本仓库的 Makefile 主要面向 CI / Linux / macOS。
# 若本机没有 make，直接用 Python 运行等价命令（下面每个目标都标注了等价写法）。

PYTHON ?= python
UVICORN_PORT ?= 8005

.PHONY: help install dev eval eval-quick reindex fetch-model fetch-model-all smoke-safety lint clean

help:
	@echo "可用目标："
	@echo "  make install          安装后端依赖"
	@echo "  make dev              启动后端（默认 8005 端口）"
	@echo "  make fetch-model      下载中文 embedding 模型 bge-small-zh-v1.5（95MB）"
	@echo "  make fetch-model-all  再下载本地 rerank 模型 bge-reranker-base（1.0GB）"
	@echo "  make reindex          用 knowledge_base/ 重建 RAG 索引"
	@echo "  make eval             运行 100 条 RAG 评测集（含 rerank）"
	@echo "  make eval-quick       只跑检索层，不做 rerank（零成本、可离线）"
	@echo "  make smoke-safety     合规模块冒烟（定级/策略/插桩/脱敏，纯本地）"
	@echo "  make clean            清理 Python 缓存"

# 本项目用 uv + pyproject.toml 管理依赖（与 start.sh 保持一致），
# 没有 requirements.txt，不要改回 pip install -r。
install:
	uv sync

dev:
	cd backend && $(PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port $(UVICORN_PORT)

# 评测集：evals/rag_eval_set.jsonl（100 条，可答 90 / 应拒答 10）
# 等价命令（无 make 时）：python scripts/rag_eval.py
eval:
	$(PYTHON) scripts/rag_eval.py

# 不调用 rerank API：适合离线环境或不想消耗额度时做回归
eval-quick:
	$(PYTHON) scripts/rag_eval.py --no-rerank

reindex:
	$(PYTHON) scripts/rag_eval.py --reindex --no-rerank

fetch-model:
	$(PYTHON) scripts/fetch_embedding_model.py --model embedding

# rerank 走本地 cross-encoder（默认），把核心检索链路挂在云端账户余额上不可接受。
# 不下载也能跑：会自动降级到百炼 API，再不行就退回 RRF 融合顺序。
fetch-model-all:
	$(PYTHON) scripts/fetch_embedding_model.py --model all

# 合规模块冒烟：定级准确性、策略矩阵、链路插桩完整性、脱敏保语义。
# 纯本地执行，不联网、不消耗任何模型额度。
smoke-safety:
	$(PYTHON) scripts/smoke_safety.py

clean:
	@find . -type d -name "__pycache__" -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
	@echo "已清理缓存"
