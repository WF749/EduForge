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
   只有用户明确说"提交""推送"时才执行。**提交前先跑通下面的 988 项验证。**

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
| 项目历程、踩过的坑与修复记录 | [`docs/PROJECT-JOURNAL.md`](docs/PROJECT-JOURNAL.md) |

## 每次修完问题都要做的一件事

在 [`docs/PROJECT-JOURNAL.md`](docs/PROJECT-JOURNAL.md) 的 **§3 问题与修复记录** 追加一条，
格式固定：

```
现象 → 根因 → 解法 → 验证 → 教训
```

为什么强制：本项目由 AI coding 从 0 到 1 完成，作者没有逐行写过每一行代码。
这份日志是作者回看系统全貌的唯一抓手 —— 不写，就等于每次都重新问一遍 AI。
顺带规则：动了架构就补 §2，遇到新的"还没解决"的坑就补 §4。

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
PYTHONPATH=backend uv run --project backend python scripts/smoke_api_contract.py        # 14 项
PYTHONPATH=backend uv run --project backend python scripts/smoke_offline_artifact.py    # 27 项
PYTHONPATH=backend uv run --project backend python scripts/smoke_teaching_review.py     # 27 项
PYTHONPATH=backend uv run --project backend python scripts/smoke_lesson_tutor.py        # 49 项
PYTHONPATH=backend uv run --project backend python scripts/smoke_lesson_docx.py         # 35 项
PYTHONPATH=backend uv run --project backend python scripts/smoke_knowledge_base.py      # 56 项
PYTHONPATH=backend uv run --project backend python scripts/smoke_rag_seed_sync.py    # 31 项
PYTHONPATH=backend uv run --project backend python scripts/smoke_teaching_workflow.py   # 209 项
PYTHONPATH=backend uv run --project backend python scripts/smoke_course_knowledge.py  # 41 项
node scripts/smoke_chat_action.mjs                                                      # 45 项
node scripts/smoke_dialogue_fields.mjs                                                  # 25 项
node scripts/smoke_lesson_intent.mjs                                                    # 65 项
node scripts/smoke_speech.mjs                                                           # 21 项
node scripts/smoke_markdown_code.mjs                                                    # 23 项
```

**当前基线：988 项全绿（70 + 77 + 29 + 40 + 14 + 53 + 37 + 14 + 27 + 27 + 49 + 35 + 56 + 31 + 41 + 209 + 45 + 25 + 65 + 21 + 23）。跑出红色必须修到绿，或明确说明为什么基线要变。**

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
- 动了产物离线检查（`backend/app/services/offline_artifact.py`）→ 必跑
  `smoke_offline_artifact.py`；它同时钉死**漏报**（CDN 引库写法一个都不能放走，
  否则拷到没网的教室才发现打不开）和**误报**（注释里的示例链接、data: URI、相对路径
  一个都不能报 —— 误报一多，这个提示就没人看了）。
- 动了语音能力（`frontend/src/composables/useSpeech.js`）→ 必跑 `node scripts/smoke_speech.mjs`。
  语音**没法在 CI 里真跑**（要麦克风、要 HTTPS、要 Chrome），所以能抽成纯逻辑的部分
  （错误码翻译、朗读前文本清洗）必须抽出来测，否则它就是一片无人验证的代码。
- 动了模型深度复查（`backend/app/services/teaching_review.py`）→ 必跑
  `smoke_teaching_review.py`。它默认关闭、平时没人触发，**正是最容易腐化成死代码的那种功能**
  （上一个这么死掉的是 `content_version_manager`），所以测试里直接开开关 + 注入假 LLM 跑通全链路。
  另有一条静态校验盯着它不许绕过 `llm_service` 直连 provider —— 出校插桩在 llm_service 里。
- 动了缺字段的中文映射（`frontend/src/utils/dialogueFields.js`）→ 必跑
  `node scripts/smoke_dialogue_fields.mjs`；它钉死的是"译不出来就原样返回、绝不编造"——
  `missing_fields` 是模型自由生成的，写死对照表必漏，而漏了的表现只是
  教师看到一串英文，**没人会报错**。
- 动了 LLM 服务的调用/兜底逻辑 → 必跑 `smoke_llm_service.py`；它钉死的是
  "模型失败后绝不静默切演示模板"以及"降级提示必须先于模板内容"，
  这类问题**不报错、不进日志**，只能靠测试发现。
- 动了工作台对话的分流（`frontend/src/utils/chatAction.js` 的 `looksLikeQuestion`）
  → 必跑 `node scripts/smoke_chat_action.mjs`。它钉死的是**「提问」和「要东西」走不同后端接口**：
  提问走问答（真的给答案），含糊诉求走状态机（澄清/确认）。历史上两类话共用一条路，
  于是所有提问都被当成"需求没说全"，教师问「什么是三角函数」拿回来的是
  「请问您想了解什么主题的知识」，再问一句就只剩「你直接说要生成什么」。
  词表宁窄勿宽：漏判只是多一次澄清往返，误判会把一句修改指令送进问答、绕掉真正的动作
  （"换成煮饺子的例子"里的"例子"就曾是这样一个误判源）。
- 动了教学工作台的问答语境（`backend/app/services/lesson_tutor.py`）→ 必跑
  `smoke_lesson_tutor.py`。它钉死的是几条**模型不会自己遵守**的行为准则：
  直接回答而不是反问、不谎称"已经生成好了"、贴住学段学科、缺信息时最多问一个。
  少写一条，界面上就会多一类"看着像坏了"的回答，而且不报错。
- 动了消息渲染管线（`frontend/src/utils/markdown.js` / `markdownCode.js`）→ 必跑
  `node scripts/smoke_markdown_code.mjs`。代码高亮**已经静默失效过一次**：
  marked 从 v5 起移除了 `highlight` 配置项，`setOptions({ highlight })` 变成被忽略的字段，
  界面上不快了但控制台不报错、构建正常、`utils/highlight.js` 里注册的 12 种语言全白注册。
  该脚本的第 5 组用例专门盯着"高亮到底有没有真的接进 marked"。
- 动了工作台布局（`frontend/src/views/WorkbenchView.vue` / `LessonContextBar.vue`）→
  没有自动化测试，**必须实机看**：对话是主舞台（占满剩余宽度）、成品是可收起的辅列、
  一屏之内能看到输入框。旧版把对话夹在 200px 侧栏和成品区之间，还留了一大片空白。
- 动了"从一句话里读课程信息"（`frontend/src/utils/lessonIntent.js`）→ 必跑
  `node scripts/smoke_lesson_intent.mjs`。它钉死的是**新手能不能开口就用**：
  教师说「生成一份浮力教案」，系统要是回「请先在顶部填好教学主题」，
  他就是被要求把刚说过的话再说一遍 —— 这是劝退的头号原因。
  两个方向都要钉：该读出来的必须读出来（主题/学科/年级/课时），
  读不出来的**必须返回空**（宁可问一句，也不能编一个主题，那会生成一整份无关教案）。
  别名表（初一→七年级、道法→道德与法治）与"宁窄勿宽"的取舍都在这条测试里。
- 动了教案导出（`llm_lesson_plan_all_stages.py` 的 `_export_to_docx`）→ 必跑
  `smoke_lesson_docx.py`。排版的问题**在界面上看不出来**，教师下载打印才发现，
  而且坏得都很安静：python-docx 默认是 **Letter 不是 A4**；
  渲染里到处 `str(v)`，模型把一条目标写成 `{"具体目标": …}` 就会把
  **Python 的 repr 印进 Word**（线上真的产出过 `{'具体目标': "能准确说出…`）；
  `- ` 伪列表在 Word 里只是破折号，多行缩进靠空格硬凑。
  测试拿这三种**真实出现过的坏输入**去建文档，再反过来查产物里没有这些痕迹。
- 动了深浅色主题（`store/theme.js`、`assets/styles/main.scss` 的 `--wb-*` token）→
  组件里**不许再写** `rgba(255,255,255,0.x)`：那套硬编码正是"浅色主题是死代码"的根因。
  新增组件一律用 token；改完必须**两个主题各看一遍**（顶栏图标切换，刷新后应保持）。
- 动了预置知识库（`knowledge_base/`）或检索评测集（`evals/rag_eval_set.jsonl`）→
  必跑 `smoke_knowledge_base.py`，并跑一次 `make eval`。
  **预置知识库是交付内容**：教师的第一次备课不该以"先上传资料"为前提。
  这类内容资产最容易被悄悄掏空（删几篇、改成占位、扩了内容却忘了更新评测集），
  没有测试的话都不会报错，只表现为"问什么都说不知道"。
  该测试钉的是资产本身：规模与分节密度、每篇自成体系、
  以及评测集与语料严格对齐（expect_terms 真在文档里、拒答题真在库外）。
- 动了种子索引的同步与来源标记（`app/rag/seed_sync.py`、retriever 的
  `clear_seed`/`ORIGIN_*`）→ 必跑 `smoke_rag_seed_sync.py`。
  它钉的三件事都属于"操作成功、数据没了"：
  ① `POST /api/rag/reindex` **只重建种子、不碰用户上传**（曾调用 `clear()`
     连 chroma collection 一起删，教师重启一次服务资料全没，接口却报成功）；
  ② origin 只有 seed/upload 两种且全项目同一口径（曾出现 source=seed 与
     origin=upload 两个字段表达同一件事，种子靠"恰好没写 origin"侥幸存活）；
  ③ 文件改了要重建、文件删了要移除（曾只看 id 在不在，改了查不到新的、
     删了还在检索旧的，两头都静默）。
- 动了教学意图 / 蓝图 / 工作流（`app/services/teaching_{intent,blueprint,workflow}.py`、
  `app/api/teaching.py`）→ 必跑 `smoke_teaching_workflow.py`。它钉的都属于
  **"操作成功、内容却是错的"**：① 台账里意图与扁平字段必须收敛成一份真值
  （曾出现同一节课两个主题，且不报错）；② 只有 `status=confirmed` 的蓝图
  才注入四路（草稿/跳过不得指导生成，响应也不许报 used=True）；
  ③ 同一节课的四路必须共用同一份知识**快照**，不是各检索一遍；
  ④ 状态恢复：`generating` 从台账读出来必须降级成 `failed(recoverable)`。
- 动了"四路生成取知识"（`app/services/course_knowledge.py`）→ 必跑
  `smoke_course_knowledge.py`。它钉的是**四路必须共用同一份课程知识上下文**：
  教案/PPT/动画/游戏此前完全不查知识库，同一节课能给出四套互不一致的说法。
  少接一路不会报错，只会让那一路悄悄退化，所以测试里有静态校验盯着四个入口。
  另有一条钉"检索失败绝不阻断生成"（生成不该因为检索抖动而失败）。
- 新增/改动知识文档的重建逻辑 → **必须走 `seed_sync.rebuild_seed_index`**。
  曾出现两套实现（API 一套、`scripts/rag_eval.py` 一套），评测脚本那份还在用
  `clear()` 与旧 metadata —— 于是"评测跑过的索引"和"线上用的索引"不是同一套，
  改了一处另一处不动，评测结果说明不了线上行为。

## 不确定的时候

- **先问，不要猜**。尤其是：要不要改架构分层、要不要加依赖、要不要动历史、要不要改默认策略。
- 发现文档与实际代码不符 → **改文档**（知识必须留在仓库里，不能只留在对话里）。
- 做了非显而易见的取舍 → 在提交信息里写清**原因**，而不只是做了什么。
