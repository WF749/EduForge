"""成品版本链 API。

给前端提供三件事：看历史、取某一版、回退。
"产生新版本"由各生成/修改接口在内部调用 ``artifact_versions.save_version``，
不走这里的 POST —— 因为版本必须和"这次改动做了什么"绑定才有意义，
把存版本暴露成独立写接口，容易出现"内容改了但没记版本"的空洞。

路由（main.py 以 /api 为前缀挂载）：
    GET  /api/artifacts/versions?lesson_id=&kind=      版本列表（只含元信息）
    GET  /api/artifacts/content?lesson_id=&kind=&v=    某一版的正文
    POST /api/artifacts/revert                         回退（非破坏性，产生新版本）
"""

from fastapi import APIRouter, Body, HTTPException, Query
from typing import Any, Dict, Optional

from ..services import artifact_versions

router = APIRouter(prefix="/artifacts", tags=["成品版本"])


def _ok(**kwargs: Any) -> Dict[str, Any]:
    return {"success": True, **kwargs}


def _fail(status: int, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail=message)


@router.get("/versions")
async def list_versions(
    lesson_id: str = Query(..., description="课程 id"),
    kind: str = Query(..., description="成品类型：lesson_plan / animation / game / ppt"),
):
    """列出一节课某种成品的版本历史（不含正文）。"""
    try:
        return _ok(**artifact_versions.list_versions(lesson_id, kind))
    except artifact_versions.ArtifactVersionError as e:
        raise _fail(400, str(e))


@router.get("/content")
async def get_content(
    lesson_id: str = Query(..., description="课程 id"),
    kind: str = Query(..., description="成品类型"),
    version: Optional[int] = Query(None, description="版本号，省略则取当前版本"),
):
    """读取某一版的正文。版本不存在返回 404，不返回空内容——避免调用方拿 None 覆盖现有内容。"""
    try:
        content = artifact_versions.get_content(lesson_id, kind, version)
    except artifact_versions.ArtifactVersionError as e:
        raise _fail(400, str(e))

    if content is None:
        raise _fail(404, "该版本不存在或内容缺失")
    return _ok(lesson_id=lesson_id, kind=kind, content=content)


@router.post("/revert")
async def revert(
    lesson_id: str = Body(..., description="课程 id"),
    kind: str = Body(..., description="成品类型"),
    version: int = Body(..., description="要回退到的版本号"),
):
    """回退到指定版本。

    不会删除任何历史：把目标版本的内容复制为一个新版本，
    note 里写明"回退到 vN"，所以回退本身也能被再回退。
    """
    try:
        meta = artifact_versions.revert_to(lesson_id, kind, version)
    except artifact_versions.ArtifactVersionError as e:
        raise _fail(400, str(e))

    return _ok(message=f"已回退到 v{version}，并记为新版本 v{meta['version']}", version=meta)
