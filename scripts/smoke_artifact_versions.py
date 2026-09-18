"""成品版本链的冒烟测试（**不调模型、不启服务**，秒级完成）。

存在的理由：版本链是"多轮迭代"的地基。它坏了的表现极其隐蔽——
不是报错，而是**教师改了一版之后回退不回去**，或者回退后把历史截断，
等他发现"我前一版写得更好的那版找不回来了"，内容已经丢了。

这里把契约钉死：
  1. 版本只增不减，回退**不删历史**（回退本身也是一个新版本）；
  2. 正文形态（dict 教案 / str HTML）原样往返，不做隐式转换；
  3. 非法 lesson_id / kind 直接拒绝——id 会进路径，不能让 '../' 拼出任意目录；
  4. 取不到版本时返回 None 而不是空内容，逼调用方自己判空，别拿它去覆盖。
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import paths  # noqa: E402
from app.api import artifact_versions as av_api  # noqa: E402
from app.services import artifact_versions as av  # noqa: E402

PASS: list = []
FAIL: list = []


def check(name: str, cond: bool, extra: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  {extra}" if extra else ""))


def raises(fn, *args, **kwargs) -> bool:
    try:
        fn(*args, **kwargs)
    except av.ArtifactVersionError:
        return True
    return False


def use_temp_dir():
    tmp = Path(tempfile.mkdtemp(prefix="eduforge-av-"))
    paths.DATA_DIR = tmp
    return tmp


# ---------------------------------------------------------------------------
def test_save_and_read() -> None:
    print("\n== 1. 存版本与读取 ==")
    v1 = av.save_version("lesson-A", "lesson_plan", {"教学目标": ["目标一"]}, note="初始版本")
    check("第一个版本号是 1", v1["version"] == 1)
    check("元信息记录正文形态为 dict", v1["shape"] == "dict")
    check("note 被保留", v1["note"] == "初始版本")

    cur = av.get_content("lesson-A", "lesson_plan")
    check("不传版本号时读当前版本", cur == {"教学目标": ["目标一"]}, f"got={cur!r}")

    v2 = av.save_version("lesson-A", "lesson_plan", {"教学目标": ["目标一", "目标二"]}, note="加一条目标")
    check("第二个版本号是 2", v2["version"] == 2)
    check("保存后当前版本前进到 2",
          av.get_content("lesson-A", "lesson_plan") == {"教学目标": ["目标一", "目标二"]})
    check("旧版本仍可原样取回（未被覆盖）",
          av.get_content("lesson-A", "lesson_plan", 1) == {"教学目标": ["目标一"]})


def test_shape_roundtrip() -> None:
    print("\n== 2. 正文形态往返 ==")
    html = "<html><body><h1>浮力</h1></body></html>"
    av.save_version("lesson-A", "animation", html, note="动画初版")
    check("字符串正文原样返回", av.get_content("lesson-A", "animation") == html)
    check("字符串的 shape 记为 str",
          av.list_versions("lesson-A", "animation")["versions"][0]["shape"] == "str")

    nested = {"a": {"b": [1, 2, {"c": None}]}}
    av.save_version("lesson-A", "game", nested)
    check("嵌套 dict 原样返回", av.get_content("lesson-A", "game") == nested)


def test_list_versions() -> None:
    print("\n== 3. 版本列表 ==")
    info = av.list_versions("lesson-A", "lesson_plan")
    check("列出 2 个版本", len(info["versions"]) == 2, f"got={len(info['versions'])}")
    check("current 指向最新", info["current"] == 2)
    check("版本号升序排列", [v["version"] for v in info["versions"]] == [1, 2])
    check("元信息不含正文（避免列表接口返回巨大响应）",
          all("content" not in v for v in info["versions"]))
    empty = av.list_versions("lesson-ZZZ", "lesson_plan")
    check("不存在的课程返回空链而非报错", empty["versions"] == [] and empty["current"] == 0)


def test_revert_is_non_destructive() -> None:
    print("\n== 4. 回退是非破坏性的 ==")
    before = av.list_versions("lesson-A", "lesson_plan")["versions"]
    meta = av.revert_to("lesson-A", "lesson_plan", 1)
    check("回退产生新版本号 3", meta["version"] == 3)
    check("note 标明来源版本", "回退到 v1" in meta["note"], f"note={meta['note']!r}")
    check("回退后当前内容等于 v1 的内容",
          av.get_content("lesson-A", "lesson_plan") == {"教学目标": ["目标一"]})
    after = av.list_versions("lesson-A", "lesson_plan")["versions"]
    check("历史没有被截断（v1/v2 都还在）", len(after) == len(before) + 1)
    check("v2 仍可取回（回退没删它）",
          av.get_content("lesson-A", "lesson_plan", 2) == {"教学目标": ["目标一", "目标二"]})

    av.revert_to("lesson-A", "lesson_plan", 3)
    check("回退本身也能被再回退", av.list_versions("lesson-A", "lesson_plan")["current"] == 4)


def test_missing_version_returns_none() -> None:
    print("\n== 5. 取不到时返回 None ==")
    check("不存在的版本号返回 None", av.get_content("lesson-A", "lesson_plan", 99) is None)
    check("版本号 0 返回 None", av.get_content("lesson-A", "lesson_plan", 0) is None)
    check("整条链不存在时返回 None", av.get_content("lesson-NOPE", "lesson_plan") is None)
    check("回退到不存在的版本要报错，不能静默成功",
          raises(av.revert_to, "lesson-A", "lesson_plan", 99))


def test_id_and_kind_guard() -> None:
    print("\n== 6. 入参守卫（id 会进路径）==")
    for bad in ("../evil", "a/b", "", "..", "a b", "x" * 65):
        check(f"拒绝非法 lesson_id {bad!r}", raises(av.save_version, bad, "lesson_plan", "x"))
    check("拒绝未登记的成品类型", raises(av.save_version, "lesson-A", "novel", "x"))
    for k in av.KINDS:
        check(f"登记的成品类型 {k} 可用", not raises(av.save_version, "lesson-A", k, "x"))


def test_atomic_and_files() -> None:
    print("\n== 7. 落盘 ==")
    d = Path(paths.DATA_DIR) / "artifact_versions" / "lesson-A" / "lesson_plan"
    check("版本链目录按 课程/类型 分层", d.is_dir())
    check("索引文件存在", (d / "index.json").is_file())
    check("每个版本一个正文文件", (d / "v1.json").is_file() and (d / "v3.json").is_file())
    check("正文文件里带 meta（便于单独审计某一版是谁在什么时候改的）",
          "meta" in __import__("json").loads((d / "v1.json").read_text(encoding="utf-8")))


def test_delete_chain() -> None:
    print("\n== 9. 删课时清掉版本正文 ==")
    lid = "lesson-del"
    av.save_version(lid, "lesson_plan", {"教学目标": ["x"]})
    av.save_version(lid, "animation", "<html></html>")
    check("两条链都建好了",
          av.get_content(lid, "lesson_plan") is not None
          and av.get_content(lid, "animation") is not None)

    check("删除 lesson_plan 链成功", av.delete_chain(lid, "lesson_plan") is True)
    check("删完读不到内容", av.get_content(lid, "lesson_plan") is None)
    check("删一条不影响另一条", av.get_content(lid, "animation") == "<html></html>")
    check("删不存在的链返回 False", av.delete_chain(lid, "game") is False)

    from app import persist
    from app.api import lesson_tasks as lt
    # 台账也要指到临时目录，别动真实数据
    persist.LESSON_TASK_STORE = Path(paths.DATA_DIR) / "lesson_tasks.json"
    asyncio.run(lt.upsert_lesson_task({"id": lid, "topic": "待删除的课"}))
    av.save_version(lid, "game", "<html>g</html>")
    r = asyncio.run(lt.delete_lesson_task(lid))
    check("删课接口顺带清掉了剩余版本链", "game" in r["cleaned_chains"], f"got={r['cleaned_chains']}")
    check("删课后 game 链也没了", av.get_content(lid, "game") is None)


def test_api_layer() -> None:
    print("\n== 8. API 层（用独立课程，避免依赖前面的版本号）==")
    lid = "lesson-api"
    av.save_version(lid, "lesson_plan", {"教学目标": ["目标一"]}, note="初版")
    av.save_version(lid, "lesson_plan", {"教学目标": ["目标一", "目标二"]}, note="加一条")

    r = asyncio.run(av_api.list_versions(lesson_id=lid, kind="lesson_plan"))
    check("列表接口 success", r["success"] is True and r["current"] == 2, f"current={r.get('current')}")

    r = asyncio.run(av_api.get_content(lesson_id=lid, kind="lesson_plan", version=1))
    check("取正文接口 success", r["success"] is True and r["content"] == {"教学目标": ["目标一"]})

    try:
        asyncio.run(av_api.get_content(lesson_id=lid, kind="lesson_plan", version=99))
        check("取不存在的版本应 404", False)
    except Exception as e:
        check("取不存在的版本应 404", getattr(e, "status_code", None) == 404, f"got={e!r}")

    try:
        asyncio.run(av_api.list_versions(lesson_id="../evil", kind="lesson_plan"))
        check("非法 id 应 400", False)
    except Exception as e:
        check("非法 id 应 400", getattr(e, "status_code", None) == 400)

    r = asyncio.run(av_api.revert(lesson_id=lid, kind="lesson_plan", version=1))
    check("回退接口 success", r["success"] is True and r["version"]["version"] == 3)
    check("回退后当前内容回到 v1",
          av.get_content(lid, "lesson_plan") == {"教学目标": ["目标一"]})


# ---------------------------------------------------------------------------
def main() -> int:
    print("=" * 64)
    print("成品版本链冒烟测试")
    print("=" * 64)
    tmp = use_temp_dir()
    try:
        for fn in (
            test_save_and_read,
            test_shape_roundtrip,
            test_list_versions,
            test_revert_is_non_destructive,
            test_missing_version_returns_none,
            test_id_and_kind_guard,
            test_atomic_and_files,
            test_delete_chain,
            test_api_layer,
        ):
            fn()
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + "=" * 64)
    print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    if FAIL:
        for name in FAIL:
            print(f"  FAIL: {name}")
    print("=" * 64)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
