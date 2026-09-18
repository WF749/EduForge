# AGENTS.md

> 这是**本仓库唯一的 AI 协作入口**。Claude Code / Cursor / Codex / Copilot / WorkBuddy 等任何 AI 编码工具，
> 动手前**先读完本文件**，再按地图去读对应文档。
> 本文件只做**目录与红线**，不写细节——细节在 `docs/` 下，按需读取，不要一次性全读进上下文。

## 项目一句话

EduForge · 教铸：面向 K-12 教师的**本地优先**多模态备课工作台。
Vue3 + FastAPI 单体，后端托管前端构建产物，教案/PPT/动画/游戏四路生成，
外加**教学合规质检（R1–R8）**与**数据出校合规（L1–L5）**两道独立关卡。

## 先记住这 9 条红线（违反即视为破坏项目）

1. **绝不能直接 `npm run build`**。`vite build` 会先清空 `frontend/dist`，而 dist 是**后端生产托管目录**
   （`backend/app/main.py` 从它读 index.html）。构建中断 = 线上前端白屏。
   正确做法见 [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md#4-前端构建)。
2. **不要重写 Git 历史、不要 force push**，除非用户明确要求并已确认远端 sha。
3. **不要提交任何密钥**。`.env`、`backend/data/runtime_config*.json`、加密密钥、聊天记录、
   `backend/data/rag_index/`、`uploads/`、`generated_*/` 一律已在 `.gitignore` 中。**不要**为了"方便"把它们加进来。
4. **不要写死本地绝对路径或真实内网地址**。示例统一用 `192.168.1.100` 这类私有地址占位。
5. **不要把过程性文档塞回仓库**：竞品分析、求职叙事、评审报告、待办清单、诊断方案不入库
   （已全部移出，见 [`docs/CONSTRAINTS.md`](docs/CONSTRAINTS.md#文档边界)）。
6. **不要破坏"只报告、不阻断"的既有约定**：教学合规闸门 `run_compliance_gate()` 异常必须吞掉，
   任何情况下不得因为质检失败而丢掉生成结果。
7. **新增 LLM 调用路径必须同时接入出校插桩**。项目历史上出现过 4 条调用链路，
   只在网关检查会让生成功能完全裸奔，见 [`docs/CONSTRAINTS.md`](docs/CONSTRAINTS.md#数据合规)。
8. **不要为了"顺手"引入新依赖**。先查 `pyproject.toml` / `frontend/package.json`，
   能复用现有能力就复用；确需新增，在 PR/提交信息里说明理由。
9. **不要擅自 `git commit` 或 `git push`**。改动留在工作区，由用户自己验证后再决定提交；
   只有用户明确说"提交""推送"时才执行。**提交前先跑通下面的 345 项验证。**

## 目录地图（按需读，不要全读）

| 我要做什么 | 读哪里 |
|---|---|
| 环境搭建、启动、常见故障 | [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) |
| 硬约束完整清单与理由 | [`docs/CONSTRAINTS.md`](docs/CONSTRAINTS.md) |
| 分层架构、模块边界、数据流 | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| 教学合规 R1–R8 规则与闸门 | README §教学合规质检 + `backend/app/services/teaching_compliance.py` |
| 数据出校 L1–L5 与四种策略 | README §数据合规 + `backend/app/safety/` |
| RAG 检索、评测集、指标 | [`docs/RAG.md`](docs/RAG.md) |
| 技术引进评估（MCP / llms.txt / 可观测等） | [`docs/TECH-EVALUATION.md`](docs/TECH-EVALUATION.md) |
| 本仓库的 Harness 机制说明 | [`docs/HARNESS.md`](docs/HARNESS.md) |

## 提交前必须跑通的验证（三条，全部纯本地、零模型额度）

```bash
# 在项目根目录执行
PYTHONPATH=backend uv run --project backend python scripts/smoke_safety.py             # 70 项
PYTHONPATH=backend uv run --project backend python scripts/smoke_teaching_compliance.py # 77 项
PYTHONPATH=backend uv run --project backend python scripts/smoke_lesson_plan.py         # 29 项
PYTHONPATH=backend uv run --project backend python scripts/smoke_lesson_tasks.py        # 40 项
PYTHONPATH=backend uv run --project backend python scripts/smoke_llm_service.py         # 14 项
PYTHONPATH=backend uv run --project backend python scripts/smoke_artifact_versions.py   # 53 项
PYTHONPATH=backend uv run --project backend python scripts/smoke_lesson_plan_revise.py  # 37 项
PYTHONPATH=backend uv run --project backend python scripts/smoke_api_contract.py        #  8 项
node scripts/smoke_chat_action.mjs                                                      # 25 项
node scripts/smoke_dialogue_fields.mjs                                                  # 25 项
```

**当前基线：378 项全绿（70 + 77 + 29 + 40 + 14 + 53 + 37 + 8 + 25 + 25）。跑出红色必须修到绿，或明确说明为什么基线要变。**

改动前端后额外确认：`git status` 里**不应出现** `frontend/dist/`（它不在版本控制内）。

## 改动后的自检习惯

- 动了生成链路（教案/PPT/动画/游戏）→ 跑对应 smoke，并确认响应里的 `compliance` 字段仍在。
- 动了课程任务台账（`backend/app/api/lesson_tasks.py`）→ 必跑 `smoke_lesson_tasks.py`；
  它钉死的是"台账只存指针不存正文""超配额淘汰后 tasks 与 order 仍一致"这类
  **失败时不报错、只是静默少数据**的契约。
- 动了 `backend/app/safety/` → 必跑 `smoke_safety.py`，它有**静态回归校验**防止插桩漏接。
- 动了合规规则 → 必须同步补**反例测试**（历史上"重力：10N""答案：3"被误判成隐私泄露，
  正则必须加 `(?<![一-龥])` 词首锚定）。
- 动了 prompt 或输出上限 → 确认 `resolve_max_tokens()` 未被改回 4096（长教案会被截断成空内容）。
- 动了成品版本链（`backend/app/services/artifact_versions.py`）→ 必跑 `smoke_artifact_versions.py`；
  它钉死的是"回退不删历史""正文形态原样往返""非法 id 不能拼进路径"这三类
  **丢了内容才发现**的契约。
- 动了教案迭代修改（`backend/app/api/lesson_plan.py` 的 `revise`）→ 必跑
  `smoke_lesson_plan_revise.py`；它钉死的是"模型没给完整教案时绝不覆盖"
  "模型漏模块要用原文补回""改坏了能回退"这三条 —— 都是**界面显示成功、内容其实没了**的事故。
- 动了对话动作路由（`frontend/src/utils/chatAction.js`）→ 必跑 `node scripts/smoke_chat_action.mjs`；
  它钉死的是"修改指令不能被判成重新生成"——判错会**静默覆盖**教师改了几轮的内容。
- 动了任何一处前端调接口的路径（`frontend/src/api/*.js`、`trackedFetch(`${BASE()}/...`)`、
  axios 实例的相对路径）→ 必跑 `smoke_api_contract.py`；它把前端写的路径逐个拿到后端路由表里查，
  钉死的是"路径写错 → POST 打到 SPA 兜底返回 405 → 前端 catch 住只说一句服务没响应"
  这种**两边各自都对、合起来静默失效**的事故（`/chat/dialogue` 就是这么坏掉的）。
- 动了缺字段的中文映射（`frontend/src/utils/dialogueFields.js`）→ 必跑
  `node scripts/smoke_dialogue_fields.mjs`；它钉死的是"译不出来就原样返回、绝不编造"——
  `missing_fields` 是模型自由生成的，写死对照表必漏，而漏了的表现只是
  教师看到一串英文，**没人会报错**。
- 动了 LLM 服务的调用/兜底逻辑 → 必跑 `smoke_llm_service.py`；它钉死的是
  "模型失败后绝不静默切演示模板"以及"降级提示必须先于模板内容"，
  这类问题**不报错、不进日志**，只能靠测试发现。

## 不确定的时候

- **先问，不要猜**。尤其是：要不要改架构分层、要不要加依赖、要不要动历史、要不要改默认策略。
- 发现文档与实际代码不符 → **改文档**（知识必须留在仓库里，不能只留在对话里）。
- 做了非显而易见的取舍 → 在提交信息里写清**原因**，而不只是做了什么。
