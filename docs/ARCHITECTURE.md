# EduForge 架构设计

> 本文档描述 EduForge 的目标架构与已落地部分，供开发者与评审者理解系统设计意图。

## 1. 设计原则

1. **本地优先（Local-first）**：默认支持 Ollama / vLLM / 内网模型，数据不出校，满足中小学与高校合规要求。
2. **诚实优先（No silent fake）**：模型调用失败必须如实暴露，任何降级产物必须显式标记 `degraded`，禁止伪装成真实生成。
3. **可观测（Observable）**：每一次 LLM 调用都可被追溯（Provider / 模型 / 耗时 / 成功或降级 / 错误原因）。
4. **可扩展（Extensible）**：Provider、Agent、Skill、MCP 工具均以插件式注册，方便二次开发。

## 2. LLM Harness 层（已落地）

位置：`backend/app/core/harness/`

```
exceptions.py      统一异常：LLMUnavailableError / LLMTimeoutError / LLMProviderError
models.py          LLMResponse（含 degraded / source / trace_id）、EmbeddingResult
tracing.py         全链路追踪（内存实现，可替换为 OpenTelemetry）
circuit_breaker.py 熔断器：连续失败达阈值后拒绝调用，避免雪崩
retry.py           指数退避重试
base.py            BaseLLMClient 抽象 + WrappedProvider（为遗留 Provider 叠加横切能力）
manager.py         LLMManager：Provider 注册中心 + 运行时配置解析 + 降级策略
adapter.py         适配器：从既有 LLMService（SQLite 配置）桥接 Harness
```

**关键设计**：`WrappedProvider` 不重写各家 Provider 的调用逻辑，而是在其上叠加
重试 / 超时 / 熔断 / 追踪 / 降级标记。这样现有生成链路可"零改动迁移"到 Harness，
同时立即获得生产级稳健性。

**降级策略**：
- `degraded=True` 的响应（如 demo、缓存命中）必须被前端明确标注；
- 真实 Provider 调用失败 → 抛出 `LLMUnavailableError`，**绝不返回模板编造内容**；
- embedding 失败 → 抛出错误，绝不返回全零向量（那会静默污染检索）。

## 3. 生成管线（进行中）

- 教案：六阶段流水线，输出标准教案要素 + Word 导出。
- PPT：LLM 生成结构 → python-pptx 排版，版式质量打磨中。
- 动画：内置 Canvas 渲染引擎（数学/生物），主流程接入中。
- 游戏：自包含可玩 HTML（计时/计分/解析），题型覆盖扩展中。

**规划中的 Critic 审查回路**：生成 → 审查 → 定向修改 → 重审（最多 3 轮），
把"一次性生成"升级为"有质量保证的生产流程"，质量评分可量化展示。

## 4. 企业级 RAG（重构中）

目标链路：

```
文档上传 → 解析(按标题/语义切分) → 本地 bge-small-zh-v1.5 向量化
        → 混合检索(BM25 + 向量) → rerank → 引用溯源 → 生成
```

- 中文优化的本地 embedding，离线可用；
- 拒答阈值基于真实相似度（修正旧版余弦/距离混用）；
- 配套 100 条评测集，`make eval` 输出 RAGAS 指标，证明"可验证"而非"自我感觉良好"。

## 5. 多 Agent 协作（规划中）

```
Orchestrator
   ├─ Planner      拆解备课任务、制定生成计划
   ├─ Researcher   RAG 检索 + 资料核实
   ├─ Designer     结构设计（课件版式 / 教案框架）
   ├─ Generator    内容生成
   ├─ Critic      质量审查（事实性 / 结构 / 学情适配）
   └─ Tutor       面向学生的讲解与答疑
```

## 6. 部署

单容器：前端静态页（Vite 构建）与后端 API（FastAPI）同源托管，
避免跨域与 baseURL 配置问题。详见 `docker-compose.yml` 与项目根 `Dockerfile`。
