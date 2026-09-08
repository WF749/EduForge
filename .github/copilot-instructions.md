# GitHub Copilot 指令入口

请先读取仓库根目录的 `AGENTS.md` —— 它是本仓库唯一的 AI 协作入口，包含 8 条红线与文档地图。
不要仅凭默认习惯生成代码。

- 硬约束与原因：`docs/CONSTRAINTS.md`
- 环境 / 启动 / 测试 / 故障排查：`docs/DEVELOPMENT.md`
- 架构：`docs/ARCHITECTURE.md`
- 技术引进评估：`docs/TECH-EVALUATION.md`
- Harness 机制：`docs/HARNESS.md`

几条最容易被违反的约束：

1. **绝不能直接 `npm run build`**：vite 会先清空 `frontend/dist`，而 dist 是后端生产托管目录。
2. 教学合规闸门 `run_compliance_gate()` **只报告、不阻断**，异常必须吞掉。
3. 新增 LLM 调用路径必须落在已有出校插桩收口点内。
4. 不要提交 `.env`、`backend/data/` 下的运行期文件、`uploads/`、`generated_*/`、`frontend/dist/`。
5. 不要把竞品分析、求职叙事、评审报告、待办清单等过程性文档加回仓库。
6. 不要写真实内网地址，示例用 `192.168.1.100` 这类保留私有地址。

提交前必跑（基线 176 项全绿）：

```bash
PYTHONPATH=backend uv run --project backend python scripts/smoke_safety.py
PYTHONPATH=backend uv run --project backend python scripts/smoke_teaching_compliance.py
PYTHONPATH=backend uv run --project backend python scripts/smoke_lesson_plan.py
```
