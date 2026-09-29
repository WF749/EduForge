"""「一节课」的任务台账 API。

为什么需要它
------------
工作台把四类产物（教案 / PPT / 动画 / 游戏）挂在"一节课"下面，但此前"这一节课"
只存在于浏览器的 localStorage 里：

  - 换浏览器、清缓存、换电脑 → 课就没了，产物也跟着失联；
  - 产物只在各自生成目录里，没有任何地方记录"它属于哪节课"；
  - 参考资料的关联关系同样只活在前端。

本模块提供稳定的课程任务记录，前端以它为准，localStorage 降级为离线兜底。

设计取舍
--------
1. **不存产物正文**，只存指针（task_id / download_url / preview_url）。文件仍归
   各自的生成目录管，避免一份数据两个真源。
2. **不接管生成流程**。这里只做台账，生成仍走各自的 /api/ppt、/api/lesson-plan
   等接口——把台账塞进生成链路会让任何一个失败都拖垮另一个。
3. **保存不全量覆盖**：只更新传上来的字段，避免并发的两个面板互相擦掉对方的产物状态。
4. **配额**：最多保留 50 节课，超出丢弃最旧的。这是一个本地备课工具，不是档案系统。
"""

import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Path, Query

from .. import persist
from ..core.logging_setup import get_logger
from ..services import artifact_versions
from ..services.teaching_intent import sync_intent_with_flat

router = APIRouter()
log = get_logger("lesson_tasks")

MAX_TASKS = 50

# 与前端 store/lesson.js 的 ARTIFACTS 保持一致
ARTIFACT_TYPES = ("lesson_plan", "ppt", "animation", "game")


def _now_ms() -> int:
    return int(time.time() * 1000)


def _slug(value: Any, max_len: int = 200) -> str:
    return str(value or "").strip()[:max_len]


def _empty_artifact() -> Dict[str, Any]:
    return {
        "status": "idle",
        "taskId": "",
        "downloadUrl": "",
        "previewUrl": "",
        "previewRoute": "",
        # 产物落在哪个生成目录 / 哪个文件名。
        # 存在的理由：历史作品是按文件目录组织的，要把它们归到"某一节课"，
        # 就必须有一个目录名 ←→ 课程 的对应关系。生成接口不知道课程 ID，
        # 所以由前端在生成完成后回填（生成响应里本来就有 task_dir / filename）。
        "originDir": "",
        "fileName": "",
        "summary": "",
        "error": "",
        "at": 0,
        "compliance": None,
    }


def _normalize_artifact(patch: Dict[str, Any]) -> Dict[str, Any]:
    """只接受已知字段，避免把整份响应（含正文）塞进台账。"""
    base = _empty_artifact()
    if not isinstance(patch, dict):
        return base
    for key in ("status", "taskId", "downloadUrl", "previewUrl", "previewRoute",
                "summary", "error", "originDir", "fileName"):
        value = patch.get(key)
        if isinstance(value, str):
            base[key] = value[:2000]
        elif value is None:
            base[key] = ""
    at = patch.get("at")
    base["at"] = int(at) if isinstance(at, (int, float)) else 0
    # 质检结论随产物留存：它只有几 KB，但刷新后是"这节课合不合规"的唯一依据。
    # 只接受 dict，防止把整份生成响应（含正文）塞进来。
    compliance = patch.get("compliance")
    base["compliance"] = compliance if isinstance(compliance, dict) else None
    return base


def _normalize_references(raw: Any) -> List[Dict[str, str]]:
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, str]] = []
    for item in raw[:20]:
        if isinstance(item, dict):
            fid = _slug(item.get("file_id"), 200)
            if fid:
                out.append({"file_id": fid, "name": _slug(item.get("name"), 200)})
        elif isinstance(item, str) and item.strip():
            out.append({"file_id": _slug(item, 200), "name": ""})
    return out


def _normalize_options(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, Any] = {}
    if isinstance(raw.get("pptTheme"), str):
        out["pptTheme"] = _slug(raw["pptTheme"], 40)
    minutes = raw.get("animationMinutes")
    if isinstance(minutes, (int, float)):
        out["animationMinutes"] = max(1, min(15, int(minutes)))
    if isinstance(raw.get("gameType"), str):
        out["gameType"] = _slug(raw["gameType"], 40)
    return out


def _normalize_teaching_intent_field(raw: Any,
                                    base: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """教学意图：**只保留结构化字段与封顶后的文本**，不存任何产物正文。

    `base` 必须传进来 —— 教学意图是**现有课程字段的视图**，不是另一份副本。
    只传 teachingIntent 本身的话，topic / grade 都不在里面，`stage` 就派生不出来，
    于是台账里存下一份学科年级齐全、唯独学段为空的残缺意图。
    """
    from ..services.teaching_intent import normalize_teaching_intent

    try:
        return normalize_teaching_intent(raw, base=base).to_dict()
    except Exception as e:  # noqa: BLE001
        # 教学意图是"锦上添花"：解析炸了不能让整节课存不进去。
        log.warning("教学意图归一化失败，已按空意图保存: %s", e)
        return {}


def _normalize_blueprint_field(raw: Any) -> Dict[str, Any]:
    """教学蓝图：只存环节结构与摘要，不存教案/PPT 正文。"""
    from ..services.teaching_blueprint import normalize_blueprint

    return normalize_blueprint(raw).to_dict()


def _restore_workflow_field(raw: Any) -> Dict[str, Any]:
    """读取（而非写入）时的归一化：把"生成中"降级成"已中断、可恢复"。

    写进去的时候必须原样保存 `generating`（否则轮询中的请求会以为自己失败了）；
    但**读出来**时进程可能早就重启了，恢复成"生成中"会让教师永远等下去。
    所以 restore 只发生在读路径上。
    """
    from ..services.teaching_workflow import normalize_workflow

    try:
        return normalize_workflow(raw, restore=True).to_dict()
    except Exception as e:  # noqa: BLE001
        log.warning("工作流状态恢复失败，按初始状态处理: %s", e)
        return {}


def _normalize_workflow_field(raw: Any) -> Dict[str, Any]:
    """工作流状态：只存状态与指针，不存产物正文。"""
    from ..services.teaching_workflow import normalize_workflow

    return normalize_workflow(raw).to_dict()


def _summary(task: Dict[str, Any]) -> Dict[str, Any]:
    artifacts = task.get("artifacts") or {}
    done = sum(1 for t in ARTIFACT_TYPES if (artifacts.get(t) or {}).get("status") == "done")
    return {
        "id": task.get("id"),
        "topic": task.get("topic", ""),
        "subject": task.get("subject", ""),
        "grade": task.get("grade", ""),
        "duration": task.get("duration", 45),
        "artifactCount": done,
        "archived": bool(task.get("archived")),
        "updatedAt": task.get("updatedAt", 0),
    }


def build_file_index() -> Dict[str, Dict[str, Dict[str, str]]]:
    """给"历史作品"用的反查表：生成目录名 / 文件名 → 所属课程。

    只读不写，且台账读不出来时返回空表而不是抛错 ——
    历史作品没有归属也能用，不该因为台账坏了就整个列表打不开。
    """
    index: Dict[str, Dict[str, Dict[str, str]]] = {"dirs": {}, "files": {}}
    try:
        store = persist.load_lesson_task_store()
    except Exception:
        return index
    for task in (store.get("tasks") or {}).values():
        lesson = {"id": task.get("id", ""), "topic": task.get("topic", "")}
        if not lesson["id"]:
            continue
        for art in (task.get("artifacts") or {}).values():
            if not isinstance(art, dict):
                continue
            origin = str(art.get("originDir") or "").strip()
            if origin:
                index["dirs"][origin] = lesson
            name = str(art.get("fileName") or "").strip()
            if name:
                index["files"][name] = lesson
    return index


@router.get("/lesson-tasks", tags=["课程任务"])
async def list_lesson_tasks(
    limit: int = Query(20, ge=1, le=MAX_TASKS),
    archived: Optional[bool] = Query(None, description="按归档状态过滤；不传表示都要"),
):
    """列出最近的课程任务（最新在前），只返回摘要。"""
    # 直接调用本函数（测试、内部复用）时，带 Query(...) 默认值的参数拿到的是
    # Query 对象而不是 None。若不归一化，下面的判断会恒为真 → 静默返回空列表，
    # 这类"不报错但没数据"的问题正是本项目反复踩过的坑。
    if not isinstance(archived, bool):
        archived = None
    store = persist.load_lesson_task_store()
    tasks = store.get("tasks") or {}
    order = [i for i in (store.get("order") or []) if i in tasks]
    # order 可能缺失/损坏：用 updatedAt 兜底排序，保证列表不会空
    if not order:
        order = sorted(tasks.keys(), key=lambda k: (tasks[k] or {}).get("updatedAt", 0), reverse=True)
    out = []
    for i in order:
        task = tasks[i]
        if archived is not None and bool(task.get("archived")) != archived:
            continue
        out.append(_summary(task))
        if len(out) >= limit:
            break
    return {"success": True, "tasks": out}


@router.post("/lesson-tasks", tags=["课程任务"])
async def upsert_lesson_task(body: Dict[str, Any] = Body(default={})):
    """创建或更新一节课。只更新传上来的字段，未传的保持原样。"""
    store = persist.load_lesson_task_store()
    tasks = store.setdefault("tasks", {})
    order = store.setdefault("order", [])

    task_id = _slug(body.get("id"), 64)
    if task_id and task_id in tasks:
        task = tasks[task_id]
        created = False
    else:
        task_id = task_id or uuid.uuid4().hex[:16]
        task = {
            "id": task_id,
            "createdAt": _now_ms(),
            "artifacts": {t: _empty_artifact() for t in ARTIFACT_TYPES},
        }
        created = True

    for key in ("topic", "subject", "grade", "difficulty", "keyPoints"):
        if key in body:
            task[key] = _slug(body[key], 2000 if key == "keyPoints" else 100)
    if "duration" in body:
        try:
            task["duration"] = max(15, min(180, int(body["duration"])))
        except (TypeError, ValueError):
            pass
    if "references" in body:
        task["references"] = _normalize_references(body["references"])
    if "archived" in body:
        task["archived"] = bool(body["archived"])
    if "options" in body:
        merged = dict(task.get("options") or {})
        merged.update(_normalize_options(body["options"]))
        task["options"] = merged

    # ---- 教学意图 / 蓝图 / 工作流（2026-09-25 新增，**全部可选**）--------
    # 三个字段都是可选的：不传就跟以前完全一样（旧请求照常工作）。
    # 关键点：**只存结构化状态、摘要与引用关系，绝不写产物正文** ——
    # 台账"只存指针不存正文"的约定不能破，否则会把教案全文复制一份进来。
    # 因此这里对三个字段都做**结构归一化 + 长度封顶**，而不是原样落库。
    if "teachingIntent" in body:
        # 以"现有任务值 + 本次提交的扁平字段"为底座，保证教学意图与
        # topic/subject/grade/duration/difficulty 是同一份真值（不另存副本）。
        # 只更新传上来的字段是既有语义：本次没传的沿用任务里已有的。
        flat_base = {
            k: body[k] if k in body else task.get(k)
            for k in ("topic", "subject", "grade", "duration", "difficulty")
        }
        if "stage" in body:
            flat_base["stage"] = body["stage"]
        task["teachingIntent"] = _normalize_teaching_intent_field(
            body["teachingIntent"], base=flat_base)

    # 双向收敛：**只要课上有教学意图，就必须与扁平字段一致**。
    # 放在 intent 块之后、且不受"本次有没有传 intent"影响 ——
    # 否则"先保存意图、之后只改主题"会留下两个主题，后续生成依据不明。
    if isinstance(task.get("teachingIntent"), dict) and task["teachingIntent"]:
        merged, flat_patch = sync_intent_with_flat(
            task["teachingIntent"],
            {k: task.get(k) for k in ("topic", "subject", "grade",
                                      "duration", "difficulty")})
        task["teachingIntent"] = merged
        for k, v in flat_patch.items():
            task[k] = v
    if "teachingBlueprint" in body:
        task["teachingBlueprint"] = _normalize_blueprint_field(body["teachingBlueprint"])
    if "workflow" in body:
        task["workflow"] = _normalize_workflow_field(body["workflow"])

    task.setdefault("artifacts", {})
    for t in ARTIFACT_TYPES:
        task["artifacts"].setdefault(t, _empty_artifact())
    task["updatedAt"] = _now_ms()

    tasks[task_id] = task
    if task_id in order:
        order.remove(task_id)
    order.insert(0, task_id)
    # 超出配额：从最早的开始丢
    while len(order) > MAX_TASKS:
        tasks.pop(order.pop(), None)

    persist.save_lesson_task_store(store)
    log.info("课程任务 %s 已%s：%s", task_id, "创建" if created else "更新", task.get("topic", ""))
    return {"success": True, "created": created, "task": task}


@router.get("/lesson-tasks/{task_id}", tags=["课程任务"])
async def get_lesson_task(task_id: str = Path(...)):
    store = persist.load_lesson_task_store()
    task = (store.get("tasks") or {}).get(_slug(task_id, 64))
    if not task:
        raise HTTPException(status_code=404, detail="课程任务不存在")
    task = dict(task)
    # 读路径上做状态恢复：持久化的"生成中"若原样返回，
    # 刷新页面后教师会看到一个永远转不完的进度条。
    if task.get("workflow"):
        task["workflow"] = _restore_workflow_field(task["workflow"])
    return {"success": True, "task": task}


@router.delete("/lesson-tasks/{task_id}", tags=["课程任务"])
async def delete_lesson_task(task_id: str = Path(...)):
    """删除台账记录。**不会**删除已导出的文件，那些仍可在"历史作品"里下载。

    但会连带清掉这门课的**成品版本链**：版本里存的是每一版的完整正文，
    属于内部副本，课程都删了还留着就是没人认领的数据。
    """
    task_id = _slug(task_id, 64)
    store = persist.load_lesson_task_store()
    tasks = store.setdefault("tasks", {})
    order = store.setdefault("order", [])
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="课程任务不存在")
    tasks.pop(task_id, None)
    if task_id in order:
        order.remove(task_id)
    persist.save_lesson_task_store(store)

    cleaned = []
    for kind in artifact_versions.KINDS:
        try:
            if artifact_versions.delete_chain(task_id, kind):
                cleaned.append(kind)
        except Exception:
            # 清版本链失败不影响台账本身已删除
            pass
    return {"success": True, "deleted": task_id, "cleaned_chains": cleaned}


@router.put("/lesson-tasks/{task_id}/artifacts/{artifact_type}", tags=["课程任务"])
async def put_artifact(
    task_id: str = Path(...),
    artifact_type: str = Path(...),
    body: Dict[str, Any] = Body(default={}),
):
    """登记/更新某一类产物的状态。生成成功、失败、重新生成都会调这里。"""
    if artifact_type not in ARTIFACT_TYPES:
        raise HTTPException(status_code=400, detail=f"未知产物类型：{artifact_type}")
    task_id = _slug(task_id, 64)
    store = persist.load_lesson_task_store()
    tasks = store.setdefault("tasks", {})
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="课程任务不存在")

    task.setdefault("artifacts", {})
    task["artifacts"][artifact_type] = _normalize_artifact(body)
    task["updatedAt"] = _now_ms()
    persist.save_lesson_task_store(store)
    return {"success": True, "artifact": task["artifacts"][artifact_type]}


@router.delete("/lesson-tasks/{task_id}/artifacts/{artifact_type}", tags=["课程任务"])
async def clear_artifact(task_id: str = Path(...), artifact_type: str = Path(...)):
    """清除某一类产物的记录（用于"重新生成"前先归零）。"""
    if artifact_type not in ARTIFACT_TYPES:
        raise HTTPException(status_code=400, detail=f"未知产物类型：{artifact_type}")
    task_id = _slug(task_id, 64)
    store = persist.load_lesson_task_store()
    task = (store.get("tasks") or {}).get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="课程任务不存在")
    task.setdefault("artifacts", {})[artifact_type] = _empty_artifact()
    task["updatedAt"] = _now_ms()
    persist.save_lesson_task_store(store)
    return {"success": True, "artifact": task["artifacts"][artifact_type]}
