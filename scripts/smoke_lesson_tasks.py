"""「一节课」台账的冒烟测试（**不调模型、不启服务**，秒级完成）。

存在的理由：台账是"这一节课"唯一的持久化真源，里面有不少归一化逻辑
（字段白名单、时长夹取、字符串截断、超配额淘汰），任何一条被改坏的表现都是
**静默的**——不报错，只是刷新后少了一节课或少了一个产物，极难排查。

这里把契约钉死：
  1. 台账只存指针，绝不把产物正文写进 JSON（否则文件会膨胀且两个真源不一致）；
  2. running 状态由前端在恢复时降级，服务端如实保存，不做自作聪明的改写；
  3. 超配额淘汰最旧的，且不能把 tasks 与 order 搞成不一致。
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi import HTTPException  # noqa: E402

from app import persist  # noqa: E402
from app.api import lesson_tasks as lt  # noqa: E402

PASS: list = []
FAIL: list = []


def check(name: str, cond: bool, extra: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  {extra}" if extra else ""))


def use_temp_store():
    """把台账指向临时文件，避免污染真实数据。"""
    tmp = Path(tempfile.mkdtemp(prefix="eduforge-lt-"))
    persist.LESSON_TASK_STORE = tmp / "lesson_tasks.json"
    return tmp


# ---------------------------------------------------------------------------
def test_upsert_creates_and_updates() -> None:
    print("\n== 1. 建课与更新 ==")
    task = asyncio.run(lt.upsert_lesson_task({
        "topic": "一次函数的图像与性质", "subject": "数学", "grade": "七年级", "duration": 45
    }))["task"]
    tid = task["id"]
    check("创建时返回 id", bool(tid))
    check("主题被保存", task["topic"] == "一次函数的图像与性质")
    for t in lt.ARTIFACT_TYPES:
        check(f"初始化产物槽位 {t}", (task["artifacts"].get(t) or {}).get("status") == "idle")

    again = asyncio.run(lt.upsert_lesson_task({"id": tid, "subject": "物理"}))
    check("同 id 再次提交是更新而非新建", again["created"] is False)
    check("更新时只覆盖传入字段（主题保留）",
          again["task"]["topic"] == "一次函数的图像与性质")
    check("更新时覆盖了学科", again["task"]["subject"] == "物理")


def test_clamping() -> None:
    print("\n== 2. 入参夹取（防脏数据）==")
    task = asyncio.run(lt.upsert_lesson_task({
        "topic": "课时边界", "duration": 999,
        "options": {"animationMinutes": 999, "pptTheme": "蓝色系"},
    }))["task"]
    check("课时上限夹到 180", task["duration"] == 180, f"(实际 {task['duration']})")

    task2 = asyncio.run(lt.upsert_lesson_task({"topic": "课时下界", "duration": 1}))["task"]
    check("课时下限夹到 15", task2["duration"] == 15, f"(实际 {task2['duration']})")
    check("动画时长夹到 15", task["options"]["animationMinutes"] == 15,
          f"(实际 {task['options'].get('animationMinutes')})")


def test_references_and_options() -> None:
    print("\n== 3. 参考资料与面板选项 ==")
    task = asyncio.run(lt.upsert_lesson_task({
        "topic": "带资料的一节课",
        "references": [{"file_id": "abc", "name": "教材.pdf"}, "xyz", {"name": "没有 id"}],
        "options": {"gameType": "选择题", "unknown": "ignored"},
    }))["task"]
    refs = task["references"]
    check("参考资料只保留有 file_id 的项", len(refs) == 2, f"(实际 {len(refs)})")
    check("纯字符串 id 被补全为对象", refs[1] == {"file_id": "xyz", "name": ""})
    check("未登记的选项被丢弃", "unknown" not in task["options"])


def test_artifact_whitelist() -> None:
    """核心：台账只存指针，绝不吞下产物正文。"""
    print("\n== 4. 产物登记（只存指针，不存正文）==")
    task = asyncio.run(lt.upsert_lesson_task({"topic": "产物登记"}))["task"]
    tid = task["id"]
    art = asyncio.run(lt.put_artifact(tid, "ppt", {
        "status": "done",
        "taskId": "ppt-1",
        "downloadUrl": "/api/ppt/download/ppt-1",
        "summary": "共 12 页",
        "html_content": "<html>整份动画正文，绝不能进台账</html>",
        "game_data": {"questions": ["很多很多题"]},
        "compliance": {"enabled": True, "score": 92},
    }))["artifact"]
    check("状态与地址被保存", art["status"] == "done" and art["taskId"] == "ppt-1")
    check("正文字段 html_content 被丢弃", "html_content" not in art)
    check("正文字段 game_data 被丢弃", "game_data" not in art)
    check("合规结论被保留（刷新后要看）", (art.get("compliance") or {}).get("score") == 92)

    got = asyncio.run(lt.get_lesson_task(tid))["task"]
    check("读回时产物状态一致", got["artifacts"]["ppt"]["status"] == "done")

    try:
        asyncio.run(lt.put_artifact(tid, "不存在的类型", {"status": "done"}))
        check("未知产物类型被拒绝", False)
    except HTTPException as e:
        check("未知产物类型被拒绝", e.status_code == 400)


def test_not_found() -> None:
    print("\n== 5. 不存在时的行为 ==")
    for coro, label in ((lt.get_lesson_task("nope"), "读取"),
                        (lt.delete_lesson_task("nope"), "删除")):
        try:
            asyncio.run(coro)
            check(f"{label}不存在的课程返回 404", False)
        except HTTPException as e:
            check(f"{label}不存在的课程返回 404", e.status_code == 404)


def test_list_and_quota() -> None:
    print("\n== 6. 列表与配额 ==")
    for i in range(lt.MAX_TASKS + 3):
        asyncio.run(lt.upsert_lesson_task({"topic": f"第 {i} 节课"}))
    listed = asyncio.run(lt.list_lesson_tasks(limit=lt.MAX_TASKS))
    check("列表不超过配额", len(listed["tasks"]) <= lt.MAX_TASKS,
          f"(实际 {len(listed['tasks'])})")
    check("列表最新在前", listed["tasks"][0]["topic"] == f"第 {lt.MAX_TASKS + 2} 节课",
          f"(实际 {listed['tasks'][0]['topic']})")

    store = persist.load_lesson_task_store()
    check("tasks 与 order 数量一致",
          len(store["tasks"]) == len(store["order"]),
          f"(tasks {len(store['tasks'])} / order {len(store['order'])})")
    check("order 中不含已淘汰的 id",
          all(i in store["tasks"] for i in store["order"]))


def test_clear_artifact() -> None:
    print("\n== 7. 清除产物（重新生成前归零）==")
    task = asyncio.run(lt.upsert_lesson_task({"topic": "待归零"}))["task"]
    tid = task["id"]
    asyncio.run(lt.put_artifact(tid, "game", {"status": "done", "taskId": "g1"}))
    art = asyncio.run(lt.clear_artifact(tid, "game"))["artifact"]
    check("清除后回到 idle", art["status"] == "idle")
    check("清除后旧 taskId 不再残留", art["taskId"] == "")


def main() -> int:
    print("课程任务台账冒烟测试（不调模型、不启服务）")
    use_temp_store()
    test_upsert_creates_and_updates()
    test_clamping()
    test_references_and_options()
    test_artifact_whitelist()
    test_not_found()
    test_list_and_quota()
    test_clear_artifact()

    print(f"\n{'=' * 64}")
    print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    if FAIL:
        print("失败项：")
        for f in FAIL:
            print(f"  - {f}")
    print("=" * 64)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
