"""All HTTP routes under /api plus helpers."""
import asyncio
import json
import shutil
import uuid
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from . import knowledge_store, llm_client, persist, web_search
from .api.system import live_models
from .core.errors import ErrorCode
from .core.llm_gateway import llm_chat
from .core.logging_setup import get_logger
from .core.providers import get_provider, resolve_base_url
from .document_extract import extract_text, resolve_uploaded_references
from .services.dialogue_manager import dialogue_manager
from .services.multimodal_analyzer import multimodal_analyzer, ModalityType
from .pathutil import resolve_under_roots
from .paths import (
    GENERATED_ANIM,
    GENERATED_CW,
    GENERATED_GAMES,
    UPLOAD_DIR,
)

router = APIRouter(prefix="/api")

log = get_logger("api.routes")


def _mask_key(k: str) -> str:
    """密钥掩码：只暴露首尾，便于用户确认"配的是哪一把"，绝不回显明文。

    明文一旦进入浏览器，就会被写进 localStorage、被浏览器扩展读到、被截图泄露。
    开源项目尤其不能假设"本地运行就安全"。
    """
    k = (k or "").strip()
    if not k:
        return ""
    if len(k) <= 12:
        return f"{k[:2]}{'*' * max(len(k) - 4, 1)}{k[-2:]}"
    return f"{k[:6]}{'*' * 6}{k[-4:]}"


def _providers_payload(cfg: Dict[str, Any]) -> Dict[str, Any]:
    keys = cfg.get("apiKeys") or {}
    active = cfg.get("provider") or "demo"
    plist = []
    for pid in (
        "dashscope",
        "openai",
        "deepseek",
        "zhipu",
        "moonshot",
        "gemini",
        "anthropic",
        "local",
        "demo",
    ):
        plist.append(
            {
                "provider": pid,
                "is_active": pid == active,
                "has_api_key": bool(keys.get(pid)),
                # 只给掩码，前端据此显示"已配置 sk-ws-****Nw"
                "key_masked": _mask_key(keys.get(pid) or ""),
                "model": (cfg.get("models") or {}).get(pid, ""),
                "base_url": (keys.get(f"{pid}Base") or keys.get("localUrl") or ""),
            }
        )
    return {
        "providers": plist,
        "provider": active,
        "temperature": cfg.get("temperature", 0.7),
        "chunkSize": cfg.get("chunkSize", 500),
        "topK": cfg.get("topK", 5),
    }


@router.get("/llm/config")
def llm_get_config():
    cfg = persist.load_runtime_config()
    if not cfg:
        cfg = {"provider": "demo", "apiKeys": {}, "models": {}, "temperature": 0.7}
    return JSONResponse(_providers_payload(cfg))


@router.post("/llm/config")
async def llm_post_config(body: Dict[str, Any]):
    cfg = persist.load_runtime_config()
    
    # 确保 cfg 有正确的结构
    if "apiKeys" not in cfg:
        cfg["apiKeys"] = {}
    if "models" not in cfg:
        cfg["models"] = {}
    
    # 处理前端发送的单个配置
    provider = body.get("provider")
    
    # 确保 provider 是有效的字符串
    if provider and isinstance(provider, str) and provider.strip():
        provider = provider.strip()
        cfg["provider"] = provider
        
        # 处理 api_key 字段（前端发送的是单个 key）
        api_key = body.get("api_key")
        if api_key is not None:
            cfg["apiKeys"][provider] = api_key
        
        # 处理 model 字段
        model = body.get("model")
        if model:
            cfg["models"][provider] = model
        
        # 处理 temperature 字段
        temperature = body.get("temperature")
        if temperature is not None:
            cfg["temperature"] = temperature
        
        # 处理 base_url 字段
        base_url = body.get("base_url")
        if base_url:
            cfg["apiKeys"][provider + "Base"] = base_url
        
        # 清理可能存在的根级别字段
        for key in ["api_key", "model"]:
            if key in cfg:
                del cfg[key]
    else:
        # 如果没有 provider，使用 save-full-config 接口
        return {"success": False, "message": "请提供 provider 参数"}
    
    persist.save_runtime_config(cfg)
    return {"success": True}


@router.post("/llm/save-full-config")
async def llm_save_full(body: Dict[str, Any]):
    """整体保存配置。

    关键语义：**空字符串 = "不修改"，显式 null = "删除"**。

    后端不向浏览器回显明文密钥，所以设置页加载时输入框必然是空的。
    若此处整体覆盖 `apiKeys`，用户只改了模型、点了保存，
    就会把**所有已配置的 Key 清空**——这正是"配置保存成功、对话却立刻失效"
    的直接原因。因此必须逐厂商合并。
    """
    cfg = persist.load_runtime_config()

    if "provider" in body:
        cfg["provider"] = body["provider"]

    if "apiKeys" in body and isinstance(body["apiKeys"], dict):
        stored = cfg.get("apiKeys")
        if not isinstance(stored, dict):
            stored = {}
        for pid, val in body["apiKeys"].items():
            if val is None:
                # 显式删除
                stored.pop(pid, None)
                continue
            if not isinstance(val, str):
                continue
            val = val.strip()
            if not val:
                # 空 = 保持原值（不覆盖、不删除）
                continue
            # 防止把后端回显的掩码串当真密钥存回去
            if "*" in val and len(val) < 200:
                continue
            stored[pid] = val
        cfg["apiKeys"] = stored

    if "models" in body and isinstance(body["models"], dict):
        models = cfg.get("models")
        if not isinstance(models, dict):
            models = {}
        for pid, val in body["models"].items():
            # 兼容旧数据：某些客户端会把模型存成 {value,label} 对象
            if isinstance(val, dict):
                val = val.get("value") or val.get("name") or ""
            if isinstance(val, str) and val.strip():
                models[pid] = val.strip()
        cfg["models"] = models

    for k in ("temperature", "embeddingModel", "chunkSize", "topK", "maxFileSize", "allowedTypes"):
        if k in body and body[k] is not None:
            cfg[k] = body[k]

    persist.save_runtime_config(cfg)

    keys = cfg.get("apiKeys") or {}
    active = cfg.get("provider") or "demo"
    return {
        "success": True,
        "message": "ok",
        "provider": active,
        "has_api_key": bool(keys.get(active)),
        "model": (cfg.get("models") or {}).get(active, ""),
    }


@router.post("/llm/test-connection")
async def llm_test(body: Dict[str, Any]):
    """真实探测厂商连通性 —— 所有厂商走同一条代码路径。

    历史缺陷：本接口原先用 if-elif 逐厂商硬编码，只覆盖 dashscope/openai/deepseek，
    智谱 / Kimi / Gemini / Claude 一律落到末尾的 `success=True 未实现探测`，
    也就是**点了测试其实什么都没测**。现在统一走 llm_gateway：
    任何厂商新增到 Provider Registry 即自动获得真实探测能力。
    """
    import asyncio

    provider = (body.get("provider") or "demo").strip()
    key = (body.get("api_key") or "").strip()
    model = (body.get("model") or "").strip()
    base_url = (body.get("base_url") or "").strip() or None

    spec = get_provider(provider)

    if spec.protocol == "demo":
        return {"success": True, "message": "演示模式无需连接", "code": "OK"}

    # 输入框留空时，回退到已保存的 Key —— 否则"保存后想复测"会无法进行
    used_saved_key = False
    if not key and spec.protocol != "local":
        saved = persist.load_runtime_config()
        key = ((saved.get("apiKeys") or {}).get(provider) or "").strip()
        used_saved_key = bool(key)

    if not key and spec.protocol != "local":
        return {
            "success": False,
            "code": ErrorCode.NO_API_KEY,
            "message": f"未配置 {spec.label} 的 API Key",
            "hint": "填入 Key 后可先测再存，也可以直接保存。",
        }

    if not model:
        saved_m = (persist.load_runtime_config().get("models") or {}).get(provider)
        model = (saved_m or "").strip()

    try:
        # 同步 httpx 调用放到线程池，避免阻塞事件循环
        text = await asyncio.to_thread(
            llm_chat,
            "只回复两个字：正常",
            purpose="connection_test",
            provider=provider,
            model=model or None,
            api_key=key or None,
            base_url=base_url,
            max_tokens=16,
            timeout=25.0,
            max_retries=0,  # 探测不做重试，快速失败给用户明确反馈
        )
        return {
            "success": True,
            "code": "OK",
            "message": f"连接正常（{spec.label} · {model or spec.default_model}）",
            "used_saved_key": used_saved_key,
            "reply": text[:50],
        }
    except Exception as e:
        code = getattr(e, "code", None) or ErrorCode.LLM_UNAVAILABLE
        hint = getattr(e, "hint", "") or ""
        detail = getattr(e, "detail", "") or ""
        msg = str(e)
        low = msg.lower()
        # 额度类错误给出可操作建议，而不是让用户对着 429 发呆
        if code == ErrorCode.QUOTA_EXCEEDED or "free tier" in low or "exhausted" in low or "quota" in low:
            hint = hint or "免费额度可能已用尽或触发限流，请到厂商控制台查看余额 / 关闭「仅使用免费额度」模式。"
        log.warning("连接测试失败 provider=%s model=%s code=%s: %s", provider, model, code, msg)
        return {
            "success": False,
            "code": code,
            "message": msg,
            "hint": hint,
            "detail": detail[:300],
        }


@router.get("/llm/models")
async def llm_models(provider: str = Query("dashscope"), api_key: Optional[str] = None):
    """获取模型列表 —— 以厂商实时返回为准。

    历史缺陷：这里曾维护一张 150 行的硬编码模型清单，结果是
    「把真实存在的 deepseek-v4-pro 判成不存在」「Gemini 地址少 /openai/ 后缀」
    这类问题的根源。模型名与价格的权威答案永远在厂商侧，本项目不再重复维护。
    """
    res = await live_models(provider=provider, api_key=api_key)
    return res


@router.get("/llm/models/live")
async def llm_models_live(provider: str = Query("dashscope"), api_key: Optional[str] = None):
    """/api/models/live 的别名，保留旧路径兼容。"""
    return await live_models(provider=provider, api_key=api_key)


@router.delete("/llm/config/{provider}")
def llm_delete(provider: str):
    cfg = persist.load_runtime_config()
    keys = cfg.get("apiKeys") or {}
    if provider in keys:
        keys[provider] = ""
    cfg["apiKeys"] = keys
    persist.save_runtime_config(cfg)
    return {"success": True}


@router.post("/config/knowledge")
def cfg_knowledge(
    chunkSize: Optional[int] = None,
    topK: Optional[int] = None,
    embeddingModel: Optional[str] = None,
):
    cfg = persist.load_runtime_config()
    if chunkSize is not None:
        cfg["chunkSize"] = chunkSize
    if topK is not None:
        cfg["topK"] = topK
    if embeddingModel:
        cfg["embeddingModel"] = embeddingModel
    persist.save_runtime_config(cfg)
    return {"success": True}


@router.post("/config/file")
def cfg_file(
    maxFileSize: Optional[int] = None,
    allowedTypes: Optional[str] = None,
):
    cfg = persist.load_runtime_config()
    if maxFileSize is not None:
        cfg["maxFileSize"] = maxFileSize
    if allowedTypes:
        cfg["allowedTypes"] = allowedTypes.split(",")
    persist.save_runtime_config(cfg)
    return {"success": True}


async def _sse_stream(body: Dict[str, Any]) -> AsyncIterator[bytes]:
    async for chunk in llm_client.stream_chat_completion(body):
        line = json.dumps({"content": chunk, "done": False}, ensure_ascii=False)
        yield f"data: {line}\n\n".encode("utf-8")
    done = json.dumps({"content": "", "done": True}, ensure_ascii=False)
    yield f"data: {done}\n\n".encode("utf-8")


def _configured_int(key: str, default: int, minimum: int, maximum: int) -> int:
    try:
        return max(minimum, min(maximum, int(persist.load_runtime_config().get(key, default))))
    except (TypeError, ValueError):
        return default


def _message_with_uploads(message: str, body: Dict[str, Any]) -> str:
    refs = resolve_uploaded_references(body.get("attachment_ids"))
    if not refs:
        return message
    reference_text = "\n\n".join(refs)
    return f"[上传的参考资料]\n{reference_text}\n\n[用户问题]\n{message}"


@router.post("/chat/analyze")
async def chat_analyze(body: Dict[str, Any]):
    """分析用户消息，进行意图识别和对话状态管理
    
    返回对话分析结果，包括是否需要追问、确认等
    """
    conversation_id = body.get("conversation_id") or str(uuid.uuid4())
    message = body.get("message", "").strip()
    
    if not message:
        return {
            "action": "error",
            "message": "消息不能为空"
        }
    
    # 使用对话管理器进行分析
    result = dialogue_manager.analyze_and_update(conversation_id, message)
    
    return {
        "conversation_id": conversation_id,
        **result
    }


@router.post("/chat/reset-dialogue")
async def reset_dialogue(body: Dict[str, Any]):
    """重置对话上下文"""
    conversation_id = body.get("conversation_id")
    if conversation_id:
        dialogue_manager.reset_context(conversation_id)
    return {"success": True}


@router.post("/chat/stream")
async def chat_stream(body: Dict[str, Any]):
    b = dict(body)
    question = b.get("message", "")
    b["message"] = _message_with_uploads(question, b)
    if b.get("use_knowledge"):
        hits = knowledge_store.query_kb(question, top_k=_configured_int("topK", 5, 1, 20))
        ctx = "\n".join(h.get("content", "") for h in hits)
        if ctx:
            b["message"] = f"[知识库参考]\n{ctx}\n\n{b['message']}"
    return StreamingResponse(_sse_stream(b), media_type="text/plain; charset=utf-8")


@router.post("/chat/vision")
async def chat_vision(body: Dict[str, Any]):
    b = dict(body)
    question = b.get("message", "")
    b["message"] = _message_with_uploads(question, b)
    if b.get("use_knowledge"):
        hits = knowledge_store.query_kb(question, top_k=_configured_int("topK", 5, 1, 20))
        ctx = "\n".join(h.get("content", "") for h in hits)
        if ctx:
            b["message"] = f"[知识库参考]\n{ctx}\n\n{b['message']}"
    return StreamingResponse(_sse_stream(b), media_type="text/plain; charset=utf-8")


@router.post("/chat/deep-thinking")
async def chat_deep(body: Dict[str, Any]):
    b = dict(body)
    question = b.get("message") or ""
    b["message"] = _message_with_uploads(question, b)
    if b.get("use_knowledge"):
        hits = knowledge_store.query_kb(question, top_k=_configured_int("topK", 5, 1, 20))
        ctx = "\n".join(h.get("content", "") for h in hits)
        if ctx:
            b["message"] = f"[知识库参考]\n{ctx}\n\n{b['message']}"
    b["message"] = "请逐步思考后回答：\n" + b["message"]
    return StreamingResponse(_sse_stream(b), media_type="text/plain; charset=utf-8")


@router.post("/chat/search")
async def chat_search(body: Dict[str, Any]):
    q = (body.get("query") or body.get("message") or "").strip()
    try:
        snippets = await web_search.search_snippets_async(q)
    except Exception as e:
        print(f"Web search error: {e}")
        snippets = ""
    inner = (
        f"[联网检索资料摘要]\n{snippets}\n\n[用户问题]\n{q}"
        if snippets
        else f"[联网检索：当前网络环境无法访问外部资源，请结合知识库和自身知识回答用户问题]\n{q}"
    )
    b = dict(body)
    if b.get("use_knowledge"):
        hits = knowledge_store.query_kb(q, top_k=_configured_int("topK", 5, 1, 20))
        ctx = "\n".join(h.get("content", "") for h in hits)
        if ctx:
            inner = f"[知识库参考]\n{ctx}\n\n" + inner
    b["message"] = _message_with_uploads(inner, b)
    return StreamingResponse(_sse_stream(b), media_type="text/plain; charset=utf-8")


@router.post("/chat/deep-search")
async def chat_deep_search(body: Dict[str, Any]):
    q = (body.get("query") or body.get("message") or "").strip()
    try:
        snippets = await web_search.search_snippets_async(q)
    except Exception as e:
        print(f"Web search error: {e}")
        snippets = ""
    ref = (
        f"[联网检索资料摘要]\n{snippets}\n\n[用户问题]\n{q}"
        if snippets
        else f"[联网检索：当前网络环境无法访问外部资源]\n{q}"
    )
    if body.get("use_knowledge"):
        hits = knowledge_store.query_kb(q, top_k=_configured_int("topK", 5, 1, 20))
        ctx = "\n".join(h.get("content", "") for h in hits)
        if ctx:
            ref = f"[知识库参考]\n{ctx}\n\n" + ref
    b = dict(body)
    b["message"] = _message_with_uploads((
        "请结合下列资料逐步推理，先简要列出要点再给出结论，并标注哪些来自检索、哪些是推断：\n\n" + ref
    ), b)
    return StreamingResponse(_sse_stream(b), media_type="text/plain; charset=utf-8")


@router.post("/chat/summarize-requirements")
async def summarize_req(body: Dict[str, Any]):
    cid = body.get("conversation_id")
    store = persist.load_chat_store()
    msgs = (store.get("messages") or {}).get(cid) or []
    text = "\n".join(m.get("content", "") for m in msgs if m.get("role") == "user")[:8000]
    raw = llm_client.blocking_chat(
        [
            {
                "role": "user",
                "content": "从以下对话中提取教学需求，只输出 JSON，键含 topic,target_audience,duration,difficulty,key_points(数组)：\n"
                + text,
            }
        ]
    )
    req = {
        "topic": "未命名课程",
        "target_audience": "高中生",
        "duration": 45,
        "difficulty": "中等",
        "key_points": [],
    }
    try:
        j = json.loads(raw[raw.find("{") : raw.rfind("}") + 1])
        req.update(j)
    except Exception:
        if text:
            req["topic"] = text[:40]
    return {"success": True, "requirements": req}


@router.post("/chat/history")
async def chat_history_post(body: Dict[str, Any]):
    cid = body.get("conversation_id")
    history = body.get("history") or []
    if not cid:
        raise HTTPException(400, "conversation_id required")
    store = persist.load_chat_store()
    store.setdefault("messages", {})[cid] = history
    titles = {c.get("id"): c.get("title") for c in store.get("conversations", [])}
    if cid not in titles.values():
        convs = store.setdefault("conversations", [])
        if not any(c.get("id") == cid for c in convs):
            convs.insert(0, {"id": cid, "title": "对话"})
    persist.save_chat_store(store)
    return {"success": True}


@router.get("/chat/history")
def chat_history_get(conversation_id: str = Query(...)):
    store = persist.load_chat_store()
    hist = (store.get("messages") or {}).get(conversation_id) or []
    return {"success": True, "history": hist}


@router.delete("/chat/history")
def chat_history_del(conversation_id: str = Query(...)):
    store = persist.load_chat_store()
    store.get("messages", {}).pop(conversation_id, None)
    store["conversations"] = [c for c in store.get("conversations", []) if c.get("id") != conversation_id]
    persist.save_chat_store(store)
    return {"success": True}


@router.get("/chat/conversations")
def chat_conversations():
    store = persist.load_chat_store()
    return {"success": True, "conversations": store.get("conversations", [])}


@router.post("/chat/send")
async def chat_send(body: Dict[str, Any]):
    return {"success": True, "reply": "请使用流式对话界面。"}


@router.post("/chat/understand-intent")
async def chat_intent(body: Dict[str, Any]):
    msg = (body.get("message") or "").strip()
    if not msg:
        return {"success": False, "intent": "unknown", "details": {}, "message": "empty message"}
    raw = llm_client.blocking_chat(
        [
            {
                "role": "user",
                "content": (
                    "你是教学场景意图分析助手。根据用户输入，只输出一个 JSON 对象，键为："
                    "intent（取值之一：courseware_generation,knowledge_qa,general,chitchat）、"
                    "confidence（0~1）、topic（字符串或空）、need_clarification（布尔）、"
                    "clarifying_questions（字符串数组，最多3条）、notes（简短说明）。\n"
                    f"用户输入：\n{msg[:6000]}"
                ),
            }
        ],
        max_tokens=600,
    )
    out: Dict[str, Any] = {
        "intent": "general",
        "confidence": 0.5,
        "topic": "",
        "need_clarification": False,
        "clarifying_questions": [],
        "notes": "",
    }
    try:
        j = json.loads(raw[raw.find("{") : raw.rfind("}") + 1])
        if isinstance(j, dict):
            out.update({k: j[k] for k in out if k in j})
    except Exception:
        if msg:
            out["topic"] = msg[:80]
            out["notes"] = "解析失败，已回退为通用意图"
    return {"success": True, "intent": out.get("intent", "general"), "details": out}


@router.post("/multimodal/analyze")
async def analyze_multimodal(body: Dict[str, Any]):
    """多模态语义分析"""
    text = body.get("text", "")
    
    if not text:
        raise HTTPException(status_code=400, detail="请提供分析内容")
    
    # 分析文本语义
    semantics = multimodal_analyzer.analyze_text_semantics(text)
    
    # 提取关键概念
    concepts = multimodal_analyzer.extract_key_concepts(text)
    
    return {
        "success": True,
        "semantics": semantics,
        "concepts": concepts,
        "message": "多模态语义分析完成"
    }


@router.post("/multimodal/cross-modal")
async def cross_modal_transform(body: Dict[str, Any]):
    """跨模态内容转换"""
    text = body.get("text", "")
    target_type = body.get("target_type", "ppt")
    
    if not text:
        raise HTTPException(status_code=400, detail="请提供源内容")
    
    # 映射目标类型
    modality_map = {
        "image": ModalityType.IMAGE,
        "video": ModalityType.VIDEO,
        "ppt": ModalityType.PPT,
        "lesson_plan": ModalityType.LESSON_PLAN
    }
    
    target_modality = modality_map.get(target_type, ModalityType.PPT)
    
    # 创建多模态内容对象
    from .services.multimodal_analyzer import MultimodalContent
    content = MultimodalContent(
        modality=ModalityType.TEXT,
        content=text
    )
    content.semantic_tags = multimodal_analyzer.analyze_text_semantics(text).get("semantic_tags", [])
    
    # 生成跨模态描述
    result = multimodal_analyzer.generate_cross_modal_description(content, target_modality)
    
    return {
        "success": True,
        "target_type": target_type,
        "result": result,
        "message": f"已生成{target_type}格式的内容描述"
    }


@router.post("/multimodal/knowledge-graph")
async def build_knowledge_graph(body: Dict[str, Any]):
    """构建知识图谱"""
    contents_data = body.get("contents", [])
    
    if not contents_data:
        raise HTTPException(status_code=400, detail="请提供内容列表")
    
    # 转换为多模态内容对象
    from .services.multimodal_analyzer import MultimodalContent
    contents = []
    for item in contents_data:
        modality_type = getattr(ModalityType, item.get("type", "TEXT").upper(), ModalityType.TEXT)
        content = MultimodalContent(
            modality=modality_type,
            content=item.get("content", "")
        )
        content.semantic_tags = multimodal_analyzer.analyze_text_semantics(content.content).get("semantic_tags", [])
        contents.append(content)
    
    # 构建知识图谱
    graph = multimodal_analyzer.create_knowledge_graph(contents)
    
    return {
        "success": True,
        "graph": graph,
        "message": "知识图谱构建完成"
    }


@router.post("/upload/file")
async def upload_file(
    file: UploadFile = File(...),
    add_to_knowledge: bool = Query(False),
):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    fid = uuid.uuid4().hex[:12]
    safe_name = Path(file.filename or "upload").name
    dest = UPLOAD_DIR / f"{fid}_{safe_name}"
    data = await file.read()
    dest.write_bytes(data)
    reg = persist.load_file_registry()
    reg.setdefault("files", {})[fid] = {
        "filename": safe_name,
        "path": str(dest),
        "size": len(data),
    }
    persist.save_file_registry(reg)
    if add_to_knowledge:
        text = extract_text(dest)
        if not (text or "").strip():
            return {
                "success": False,
                "message": "无法从文件中提取文本（可能为扫描版 PDF 或加密文档），请换可复制文本的 PDF/Word。",
                "file_id": fid,
                "filename": safe_name,
            }
        chunk_size = _configured_int("chunkSize", 500, 100, 1000)
        chunks = knowledge_store.chunk_text(text, size=chunk_size)
        did = knowledge_store.doc_id_for_upload(fid)
        knowledge_store.add_chunks(did, safe_name, chunks, chunk_size=chunk_size)
    return {"success": True, "file_id": fid, "filename": safe_name}


@router.get("/upload/files")
def upload_files_list():
    reg = persist.load_file_registry()
    files = []
    for fid, meta in (reg.get("files") or {}).items():
        files.append({"file_id": fid, "filename": meta.get("filename"), "size": meta.get("size", 0)})
    return {"success": True, "files": files}


@router.post("/upload/process/{file_id}")
def upload_process(file_id: str):
    reg = persist.load_file_registry()
    meta = (reg.get("files") or {}).get(file_id)
    if not meta:
        raise HTTPException(404, "file not found")
    path = Path(meta["path"])
    text = extract_text(path)
    return {"success": True, "text_length": len(text)}


@router.post("/knowledge/add-file/{file_id}")
def knowledge_add_file(file_id: str):
    reg = persist.load_file_registry()
    meta = (reg.get("files") or {}).get(file_id)
    if not meta:
        raise HTTPException(404, "file not found")
    path = Path(meta["path"])
    text = extract_text(path)
    if not (text or "").strip():
        return {
            "success": False,
            "message": "无法提取文本，知识库未写入。请使用可复制文字的 PDF/Word。",
        }
    chunk_size = _configured_int("chunkSize", 500, 100, 1000)
    chunks = knowledge_store.chunk_text(text, size=chunk_size)
    did = knowledge_store.doc_id_for_upload(file_id)
    knowledge_store.add_chunks(did, meta["filename"], chunks, chunk_size=chunk_size)
    return {"success": True, "document_id": did}


@router.get("/knowledge/stats")
def knowledge_stats():
    return knowledge_store.stats()


@router.get("/knowledge/documents")
def knowledge_docs(limit: int = Query(100)):
    return {"success": True, "documents": knowledge_store.list_documents(limit)}


@router.post("/knowledge/query")
async def knowledge_query(body: Dict[str, Any]):
    q = body.get("query") or ""
    top_k = int(body.get("top_k") or _configured_int("topK", 5, 1, 20))
    results = knowledge_store.query_kb(q, top_k=top_k)
    return {"success": True, "results": results}


@router.delete("/knowledge/document/{doc_id:path}")
def knowledge_del_doc(doc_id: str):
    ok = knowledge_store.delete_document(doc_id)
    return {"success": ok}


@router.delete("/knowledge/clear")
def knowledge_clear():
    knowledge_store.clear_all()
    return {"success": True}


def _scan_dir(base: Path, path_prefix: str, label: str) -> List[Dict[str, Any]]:
    if not base.exists():
        return []
    groups = []
    for d in sorted(base.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        files = []
        for f in d.iterdir():
            if f.is_file():
                t = "other"
                if f.suffix.lower() == ".pptx":
                    t = "pptx"
                elif f.suffix.lower() == ".docx":
                    t = "docx"
                elif f.suffix.lower() == ".html":
                    t = "html"
                files.append({"name": f.name, "type": t, "size": f.stat().st_size})
        rel = f"{path_prefix}/{d.name}".replace("\\", "/")
        groups.append({"dir": d.name, "path": rel, "label": label, "files": files})
    return groups


def _label_courseware_group(files: List[Dict[str, Any]]) -> str:
    types = {f.get("type") for f in files}
    if "pptx" in types:
        return "课件"
    if "docx" in types:
        return "教案"
    return "课件"


@router.get("/courseware/files")
def courseware_files():
    out: List[Dict[str, Any]] = []
    cw = _scan_dir(GENERATED_CW, "generated_courseware", "课件")
    for g in cw:
        g["label"] = _label_courseware_group(g["files"])
    out.extend(cw)
    out.extend(_scan_dir(GENERATED_GAMES, "generated_games", "游戏"))
    out.extend(_scan_dir(GENERATED_ANIM, "generated_animations", "动画"))
    out.sort(key=lambda x: x["dir"], reverse=True)
    return {"success": True, "files": out}


@router.delete("/courseware/files/{dirname:path}")
def courseware_files_del(dirname: str):
    name = dirname.strip().strip("/").replace("\\", "/")
    name = Path(name).name
    for base in (GENERATED_CW, GENERATED_GAMES, GENERATED_ANIM):
        try:
            br = base.resolve()
        except Exception:
            continue
        target = (br / name).resolve()
        try:
            target.relative_to(br)
        except ValueError:
            continue
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
            return {"success": True}
    raise HTTPException(404, "not found")


@router.get("/courseware/download/{fmt}")
def courseware_download(
    fmt: str,
    task_dir: str = Query(""),
    topic: str = Query(""),
):
    if not task_dir:
        raise HTTPException(400, "task_dir required")
    roots = [GENERATED_CW.resolve(), GENERATED_GAMES.resolve(), GENERATED_ANIM.resolve()]
    p = resolve_under_roots(task_dir, roots)
    if not p:
        raise HTTPException(404, "path not found")
    if fmt == "pptx":
        for f in p.glob("*.pptx"):
            return FileResponse(f, filename=f.name)
    if fmt == "docx":
        for f in p.glob("*.docx"):
            return FileResponse(f, filename=f.name)
    raise HTTPException(404, "file not found")


# ChatView typo: /api/api/llm/test-connection
@router.post("/api/llm/test-connection")
async def llm_test_dup(body: Dict[str, Any]):
    return await llm_test(body)
