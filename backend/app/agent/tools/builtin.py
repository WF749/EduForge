"""EduForge 内置工具集。

选取原则（对应"多 Agent 架构要匹配实际业务，不能为炫技而堆叠"）
--------------------------------------------------------------
每个工具都对应教师备课流程中**真实存在的动作**：
  检索资料 → 生成教案/课件 → 出题 → 保存到本地产物
没有为了"看起来智能"而堆砌的无用工具。

所有工具对内部服务做**防御式导入**：某个子系统不可用时，
工具返回明确失败而非让整个 Agent 崩溃。
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import RiskLevel, ToolResult, registry

# ---------------------------------------------------------------------------
# 1. 知识检索
# ---------------------------------------------------------------------------


@registry.register(
    name="knowledge_search",
    description="在本项目知识库中检索教学相关资料（教材、课标、已上传文档）。适用于需要依托已有资料回答或备课时。",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "检索关键词或问题"},
            "top_k": {"type": "integer", "description": "返回条数，默认 5"},
        },
        "required": ["query"],
    },
    category="retrieval",
    timeout_s=30.0,
    examples=["knowledge_search(query='初中物理 浮力 教学设计', top_k=5)"],
)
def knowledge_search(query: str, top_k: int = 5) -> ToolResult:
    """走企业级 RAG：混合检索（向量+BM25）→ 重排序 → 拒答阈值 → 引用溯源。

    相比旧的 `services/rag_service`（英文 embedding + 纯向量 + 无阈值），
    这里取到的片段有来源、有标题路径，且**不相关时明确拒答**，
    从而避免把无关上下文塞给模型导致编造。
    """
    if not query or not query.strip():
        return ToolResult.failure("检索词不能为空")

    try:
        from ...rag.retriever import get_retriever
    except Exception as e:  # noqa: BLE001
        return ToolResult.failure(f"知识库服务不可用: {e}")

    try:
        result = get_retriever().retrieve(
            query.strip(), top_k=max(1, min(int(top_k or 5), 20))
        )
    except Exception as e:  # noqa: BLE001
        return ToolResult.failure(f"知识库检索失败: {e}")

    # 拒答不是错误，但必须让上层知道"本次回答没有资料依据"，
    # 否则 Writer 会拿着空上下文凭空作答。
    if result.refused:
        return ToolResult.partial(
            [],
            result.refuse_reason or "知识库中未检索到相关内容，回答将不依赖已有资料",
        )

    normalized: List[Dict[str, Any]] = []
    for h in result.hits:
        md = h.metadata or {}
        normalized.append({
            "content": h.raw_text,
            "source": h.source or md.get("filename") or "知识库",
            "heading_path": h.heading_path,
            "citation": h.citation(),
            "subject": md.get("subject", ""),
            "topic": md.get("topic", ""),
            "score": round(h.score, 4),
            "vector_score": round(h.vector_score, 4),
            "rerank_score": None if h.rerank_score is None else round(h.rerank_score, 4),
        })

    meta: Dict[str, Any] = {
        "count": len(normalized),
        "rerank": result.rerank_backend,
    }
    if result.degraded:
        meta["note"] = "；".join(result.degrade_reasons)
    return ToolResult.success(normalized, **meta)


# ---------------------------------------------------------------------------
# 2. 联网搜索
# ---------------------------------------------------------------------------


@registry.register(
    name="web_search",
    description="联网搜索最新教学资讯、政策、真题等。仅在知识库无结果或需要实时信息时使用，注意控制调用次数。",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"},
            "max_results": {"type": "integer", "description": "最多返回条数，默认 5"},
        },
        "required": ["query"],
    },
    category="retrieval",
    timeout_s=45.0,
)
def web_search(query: str, max_results: int = 5) -> ToolResult:
    if not query or not query.strip():
        return ToolResult.failure("搜索词不能为空")
    try:
        from ... import web_search as ws
    except Exception as e:
        return ToolResult.failure(f"搜索模块不可用: {e}")

    try:
        import asyncio
        fn = getattr(ws, "search_snippets_async", None) or getattr(ws, "search_snippets", None)
        if fn is None:
            return ToolResult.failure("搜索模块缺少可用入口")
        if asyncio.iscoroutinefunction(fn):
            snippets = asyncio.run(fn(query.strip()))
        else:
            snippets = fn(query.strip())
    except Exception as e:
        return ToolResult.failure(f"联网搜索失败: {e}")

    items = list(snippets or [])[: max(1, min(int(max_results or 5), 10))]
    if not items:
        return ToolResult.partial([], "未搜索到结果")
    return ToolResult.success(items, count=len(items))


# ---------------------------------------------------------------------------
# 3. 本地文件清单
# ---------------------------------------------------------------------------


@registry.register(
    name="list_uploaded_files",
    description="列出用户已上传的文件（教材、试卷、参考资料等），便于决定要解析哪些材料。",
    parameters={"type": "object", "properties": {}},
    category="resource",
    timeout_s=15.0,
)
def list_uploaded_files() -> ToolResult:
    try:
        from ... import persist
        reg = persist.load_file_registry() or {}
        files = reg.get("files") or {}
    except Exception as e:
        return ToolResult.failure(f"读取文件清单失败: {e}")
    items = []
    for fid, meta in list(files.items())[:50]:
        if isinstance(meta, dict):
            items.append({"id": fid, "name": meta.get("name") or meta.get("filename"), "size": meta.get("size")})
        else:
            items.append({"id": fid, "name": str(meta)})
    return ToolResult.success(items, count=len(items))


# ---------------------------------------------------------------------------
# 4. 生成教案
# ---------------------------------------------------------------------------


@registry.register(
    name="generate_lesson_plan",
    description="生成结构化教案（含教学目标、重难点、教学环节、时间分配、板书设计）。需要联网调用大模型，较慢。",
    parameters={
        "type": "object",
        "properties": {
            "subject": {"type": "string", "description": "学科，如 初中物理"},
            "topic": {"type": "string", "description": "课题，如 浮力的产生原因"},
            "grade": {"type": "string", "description": "年级/学段，如 八年级"},
            "duration_min": {"type": "integer", "description": "课时长度（分钟），默认 45"},
            "objectives": {"type": "string", "description": "补充的教学目标或特殊要求，可为空"},
        },
        "required": ["subject", "topic"],
    },
    risk=RiskLevel.MODERATE,
    requires_llm=True,
    category="generation",
    timeout_s=600.0,
)
def generate_lesson_plan(
    subject: str,
    topic: str,
    grade: str = "",
    duration_min: int = 45,
    objectives: str = "",
) -> ToolResult:
    if not subject.strip() or not topic.strip():
        return ToolResult.failure("学科与课题不能为空")
    try:
        from ...services.llm_lesson_plan_all_stages import generate_full_lesson_plan
    except Exception as e:
        return ToolResult.failure(f"教案生成服务不可用: {e}")
    try:
        result = generate_full_lesson_plan(
            subject=subject.strip(),
            topic=topic.strip(),
            grade=grade.strip(),
            duration_min=int(duration_min or 45),
            objectives=objectives.strip(),
        )
    except Exception as e:
        return ToolResult.failure(f"教案生成失败: {e}")
    return ToolResult.success(result)


# ---------------------------------------------------------------------------
# 5. 生成课件
# ---------------------------------------------------------------------------


@registry.register(
    name="generate_courseware",
    description="生成课件（PPT）内容大纲与页面结构。需要联网调用大模型，较慢。",
    parameters={
        "type": "object",
        "properties": {
            "subject": {"type": "string", "description": "学科"},
            "topic": {"type": "string", "description": "课题"},
            "grade": {"type": "string", "description": "年级"},
            "page_count": {"type": "integer", "description": "期望页数，默认 12"},
            "style": {"type": "string", "description": "风格偏好，可为空"},
        },
        "required": ["subject", "topic"],
    },
    risk=RiskLevel.MODERATE,
    requires_llm=True,
    category="generation",
    timeout_s=900.0,
)
def generate_courseware(
    subject: str,
    topic: str,
    grade: str = "",
    page_count: int = 12,
    style: str = "",
) -> ToolResult:
    if not subject.strip() or not topic.strip():
        return ToolResult.failure("学科与课题不能为空")
    try:
        from ...services.courseware_generator_v2 import generate_courseware_v2
    except Exception:
        try:
            from ...services.courseware_generator import generate_courseware as generate_courseware_v2
        except Exception as e:
            return ToolResult.failure(f"课件生成服务不可用: {e}")
    try:
        result = generate_courseware_v2(
            subject=subject.strip(),
            topic=topic.strip(),
            grade=grade.strip(),
            page_count=int(page_count or 12),
            style=style.strip(),
        )
    except Exception as e:
        return ToolResult.failure(f"课件生成失败: {e}")
    return ToolResult.success(result)


# ---------------------------------------------------------------------------
# 6. 出题
# ---------------------------------------------------------------------------


@registry.register(
    name="generate_exercises",
    description="按知识点生成练习题（含参考答案与解析），支持选择/填空/解答等题型。",
    parameters={
        "type": "object",
        "properties": {
            "subject": {"type": "string", "description": "学科"},
            "topic": {"type": "string", "description": "知识点/课题"},
            "grade": {"type": "string", "description": "年级"},
            "count": {"type": "integer", "description": "题目数量，默认 5"},
            "question_types": {"type": "string", "description": "题型，逗号分隔，如 选择,填空,解答"},
            "difficulty": {"type": "string", "description": "难度：容易/中等/较难，默认中等"},
        },
        "required": ["subject", "topic"],
    },
    risk=RiskLevel.MODERATE,
    requires_llm=True,
    category="generation",
    timeout_s=300.0,
)
def generate_exercises(
    subject: str,
    topic: str,
    grade: str = "",
    count: int = 5,
    question_types: str = "选择,填空,解答",
    difficulty: str = "中等",
) -> ToolResult:
    from ...core.llm_gateway import llm_chat

    # 容错：LLM 可能传数组 ["选择","填空"] 或字符串 "选择,填空"
    if isinstance(question_types, (list, tuple)):
        types = [str(t).strip() for t in question_types if str(t).strip()]
    else:
        types = [t.strip() for t in str(question_types or "").split(",") if t.strip()]
    types = types or ["选择", "解答"]
    prompt = (
        f"你是资深{subject}教师。请围绕「{topic}」为{grade or '对应年级'}出题。\n"
        f"数量：{int(count)} 题；题型：{'、'.join(types)}；难度：{difficulty}。\n"
        "要求：每题给出【题目】【参考答案】【解析】三部分，解析需点明考查的知识点。\n"
        "只输出题目内容，不要寒暄。"
    )
    try:
        text = llm_chat(prompt, purpose="generate_exercises")
    except Exception as e:
        return ToolResult.failure(f"出题失败: {e}")
    return ToolResult.success({"subject": subject, "topic": topic, "exercises": text})


# ---------------------------------------------------------------------------
# 7. 保存产物
# ---------------------------------------------------------------------------


@registry.register(
    name="save_artifact",
    description="把生成的内容保存为本地文件（Markdown/JSON），便于用户下载与复用。",
    parameters={
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "文件名，如 浮力-教案.md"},
            "content": {"type": "string", "description": "文件内容"},
            "folder": {"type": "string", "description": "子目录，默认 generated_lesson_plans"},
        },
        "required": ["filename", "content"],
    },
    risk=RiskLevel.MODERATE,
    category="output",
    timeout_s=30.0,
)
def save_artifact(filename: str, content: str, folder: str = "generated_lesson_plans") -> ToolResult:
    from ...paths import GENERATED_LP

    safe_folder = (folder or "generated_lesson_plans").strip().strip("/\\")
    # 防目录穿越
    if ".." in safe_folder or safe_folder.startswith("/"):
        return ToolResult.failure("非法的目录名")
    base = GENERATED_LP.parent / safe_folder
    safe_name = Path(filename).name
    if not safe_name:
        return ToolResult.failure("非法的文件名")
    try:
        base.mkdir(parents=True, exist_ok=True)
        path = base / safe_name
        path.write_text(content, encoding="utf-8")
    except Exception as e:
        return ToolResult.failure(f"保存失败: {e}")
    return ToolResult.success({"path": str(path), "filename": safe_name})


# ---------------------------------------------------------------------------
# 8. 高风险示例：发送邮件（必须人工确认）
# ---------------------------------------------------------------------------


@registry.register(
    name="send_email",
    description="发送邮件（如把教案发给同事/教研组）。属于高风险操作，必须人工确认后才会真正发送。",
    parameters={
        "type": "object",
        "properties": {
            "to": {"type": "string", "description": "收件人邮箱"},
            "subject": {"type": "string", "description": "邮件标题"},
            "body": {"type": "string", "description": "邮件正文"},
        },
        "required": ["to", "subject", "body"],
    },
    risk=RiskLevel.HIGH,
    category="external",
    timeout_s=60.0,
)
def send_email(to: str, subject: str, body: str) -> ToolResult:
    """高风险工具示例。

    未配置邮件服务时**如实报错**，绝不假装发送成功 ——
    "演示/未实现"必须显式标记，这是本项目开源诚信的底线。
    """
    import os
    from ...core.errors import ErrorCode

    if not os.getenv("SMTP_HOST"):
        # 如实报错而不是假装成功：未实现的外部副作用绝不能伪造成功回执
        return ToolResult.failure(
            "未配置邮件服务（缺少 SMTP_HOST 等环境变量），邮件未发送。",
            ErrorCode.HUMAN_APPROVAL_REQUIRED,
        )
    return ToolResult.failure("邮件发送能力尚未接入，邮件未发送。", ErrorCode.HUMAN_APPROVAL_REQUIRED)


# ---------------------------------------------------------------------------
# 9. 时间工具（低成本，常用于相对时间推理）
# ---------------------------------------------------------------------------


@registry.register(
    name="get_current_time",
    description="获取当前日期与时间，用于需要相对时间（本周、本月）的任务。",
    parameters={"type": "object", "properties": {}},
    category="utility",
    timeout_s=5.0,
)
def get_current_time() -> ToolResult:
    return ToolResult.success({
        "iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "date": time.strftime("%Y-%m-%d"),
        "weekday": time.strftime("%A"),
    })
