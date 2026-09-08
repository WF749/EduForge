# Claude Code 入口

**先读 [`AGENTS.md`](AGENTS.md)。** 它是本仓库唯一的 AI 协作入口，包含 8 条红线与文档地图。

- 硬约束完整版：[`docs/CONSTRAINTS.md`](docs/CONSTRAINTS.md)
- 环境/启动/测试/故障排查：[`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md)
- 架构：[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- 技术引进评估：[`docs/TECH-EVALUATION.md`](docs/TECH-EVALUATION.md)
- 本仓库的 Harness 机制：[`docs/HARNESS.md`](docs/HARNESS.md)

提交前必跑（基线 176 项全绿）：

```bash
PYTHONPATH=backend uv run --project backend python scripts/smoke_safety.py
PYTHONPATH=backend uv run --project backend python scripts/smoke_teaching_compliance.py
PYTHONPATH=backend uv run --project backend python scripts/smoke_lesson_plan.py
```

**最高优先级红线：绝不能直接 `npm run build`**（会清空后端生产托管目录 `frontend/dist`）。
