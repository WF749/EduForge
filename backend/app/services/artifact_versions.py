"""成品版本链：一节课的一种成品（教案/动画/游戏…）在时间轴上的所有版本。

为什么单独做这一套
------------------
仓库里原本有三套互不相通的"版本"机制：

1. ``content_version_manager`` —— 通用内容项版本，**没有任何前端调用**，
   且每次修改都自动把全文写回知识库（改一版就往 RAG 里塞一篇，越改越脏）；
2. PPT 的 ``task_dir/versions.json`` —— 能用，但绑死在后台任务目录上，
   教案/动画/游戏用不了；
3. ``/lesson-plan/modify`` —— 只把修改结果放在响应里返回，**不落盘**，
   刷新即丢，也没有"回退到上一版"这回事。

本模块把 (lesson_id, kind) 作为版本链的主键，统一第 2、3 种场景：
教案、动画、游戏共用同一套存储与回退语义。

刻意的设计选择
--------------
- **只存正文，不做知识库回流**。回流是调用方的决定，不是版本系统的副作用。
- **回退是非破坏性的**：回退不删除任何版本，而是把目标版本的内容
  复制成一个新版本（note 里写明来源）。这样"回退错了"还能再回退回来，
  也避免了"回退后历史被截断"导致无法审计。
- **正文支持 dict 与 str**：教案是 12 模块的 dict，动画/游戏是 HTML 字符串。
  统一用 JSON 落盘，读取时按写入时的形态原样返回，不做隐式转换。
- **写入走 ``core.json_store``**：原子替换 + 损坏可回滚。原
  ``content_version_manager`` 用裸 ``open(..., "w")``，写到一半崩了就是坏文件。
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .. import paths
from ..core.json_store import atomic_write_json, read_json

# 允许的成品类型。新增类型必须显式登记 —— 否则 lesson_id 路径会被拼成任意目录。
KINDS = ("lesson_plan", "animation", "game", "ppt")

_SAFE_ID = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


class ArtifactVersionError(ValueError):
    """版本链操作的入参错误（id 非法、kind 未登记、版本不存在）。"""


def _check_id(value: str, what: str) -> str:
    v = (value or "").strip()
    if not _SAFE_ID.match(v):
        raise ArtifactVersionError(f"{what} 非法：{value!r}（只允许字母数字下划线短横线，1-64 字符）")
    return v


def _check_kind(kind: str) -> str:
    k = (kind or "").strip()
    if k not in KINDS:
        raise ArtifactVersionError(f"成品类型未登记：{kind!r}（已登记：{', '.join(KINDS)}）")
    return k


def _chain_dir(lesson_id: str, kind: str) -> Path:
    return Path(paths.DATA_DIR) / "artifact_versions" / lesson_id / kind


def _index_path(lesson_id: str, kind: str) -> Path:
    return _chain_dir(lesson_id, kind) / "index.json"


def _content_path(lesson_id: str, kind: str, version: int) -> Path:
    return _chain_dir(lesson_id, kind) / f"v{version}.json"


def _read_index(lesson_id: str, kind: str) -> Dict[str, Any]:
    return read_json(_index_path(lesson_id, kind), {"current": 0, "versions": []})


def _write_index(lesson_id: str, kind: str, index: Dict[str, Any]) -> None:
    atomic_write_json(_index_path(lesson_id, kind), index)


def save_version(
    lesson_id: str,
    kind: str,
    content: Any,
    *,
    note: str = "",
    author: str = "teacher",
) -> Dict[str, Any]:
    """写入一个新版本，并把它设为当前版本。

    返回该版本的元信息（不含正文，正文通常很大）。
    """
    lesson_id = _check_id(lesson_id, "课程 id")
    kind = _check_kind(kind)

    index = _read_index(lesson_id, kind)
    versions: List[Dict[str, Any]] = index.get("versions") or []
    version = (max((v.get("version", 0) for v in versions), default=0)) + 1

    meta = {
        "version": version,
        "timestamp": time.time(),
        "author": author,
        "note": (note or "").strip()[:500],
        # 正文形态：dict（教案）/ str（HTML）。读取时按它决定是否 json.dumps。
        "shape": "dict" if isinstance(content, dict) else "str",
    }

    # 先写正文再写索引：索引指向的版本必须保证正文已落盘（否则读到空版本）。
    atomic_write_json(
        _content_path(lesson_id, kind, version),
        {"meta": meta, "content": content},
        keep_backup=False,  # 版本文件本身不可变，无需 .bak
    )
    versions.append(meta)
    index["versions"] = versions
    index["current"] = version
    _write_index(lesson_id, kind, index)
    return dict(meta)


def get_content(lesson_id: str, kind: str, version: Optional[int] = None) -> Any:
    """读取指定版本的正文；version 为空则读当前版本。

    版本不存在或正文文件缺失时返回 ``None`` —— 调用方必须自己判空，
    不要拿 None 去覆盖现有内容。
    """
    lesson_id = _check_id(lesson_id, "课程 id")
    kind = _check_kind(kind)

    index = _read_index(lesson_id, kind)
    if version is None:
        version = index.get("current") or 0
    version = int(version)
    if version <= 0:
        return None

    data = read_json(_content_path(lesson_id, kind, version), None)
    if not isinstance(data, dict):
        return None
    return data.get("content")


def list_versions(lesson_id: str, kind: str) -> Dict[str, Any]:
    """列出版本链（只含元信息，不含正文）。"""
    lesson_id = _check_id(lesson_id, "课程 id")
    kind = _check_kind(kind)

    index = _read_index(lesson_id, kind)
    versions = sorted(index.get("versions") or [], key=lambda v: v.get("version", 0))
    return {
        "lesson_id": lesson_id,
        "kind": kind,
        "current": index.get("current") or 0,
        "versions": versions,
    }


def revert_to(lesson_id: str, kind: str, version: int, *, author: str = "teacher") -> Dict[str, Any]:
    """回退到指定版本。

    非破坏性：不删任何历史，把目标版本正文复制为新版本，note 标明来源。
    """
    lesson_id = _check_id(lesson_id, "课程 id")
    kind = _check_kind(kind)

    target = int(version or 0)
    content = get_content(lesson_id, kind, target)
    if content is None:
        raise ArtifactVersionError(f"版本 v{target} 不存在或内容缺失")

    return save_version(
        lesson_id,
        kind,
        content,
        note=f"回退到 v{target}",
        author=author,
    )


def delete_chain(lesson_id: str, kind: str) -> bool:
    """删除整条版本链。仅在课程被彻底删除时调用。"""
    import shutil

    lesson_id = _check_id(lesson_id, "课程 id")
    kind = _check_kind(kind)
    d = _chain_dir(lesson_id, kind)
    if not d.exists():
        return False
    shutil.rmtree(d, ignore_errors=True)
    return not d.exists()
