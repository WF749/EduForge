"""教案「按指令修改」的冒烟测试（**不调模型**，秒级完成）。

存在的理由：多轮迭代是这套系统的主线，而它的失败模式全是**静默**的——
教师说一句"第三段太难换个例子"，界面显示"修改成功"，但：

  - 模型只回了它改动的那两个模块，其余 11 个模块凭空消失；
  - 或者模型压根没返回完整教案，旧内容被空 dict 覆盖；
  - 或者改完发现更差，想回退，却发现根本没有历史。

这三类事故在 2026-09-06 都以另一种形态发生过（"生成成功但内容全空"）。
这里把契约钉死，防止它们换件衣服回来。

测试用假的 generator 顶掉真实模型调用，因此不消耗任何额度。
"""
from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import paths  # noqa: E402
from app.api import lesson_plan as lp  # noqa: E402
from app.services import artifact_versions as av  # noqa: E402

PASS: list = []
FAIL: list = []


def check(name: str, cond: bool, extra: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  {extra}" if extra else ""))


BASE_PLAN: Dict[str, Any] = {
    "教案基本信息": {"课题": "浮力", "学科": "物理", "年级": "八年级", "课时": 1},
    "教学目标": ["理解浮力产生的原因", "会用阿基米德原理解释现象"],
    "教学重难点": {"重点": "阿基米德原理", "难点": "浮力成因的受力分析"},
    "教学过程设计": [
        {"环节": "导入", "内容": "提问：为什么铁船能浮在水面？"},
        {"环节": "讲授", "内容": "推导 F浮 = ρ液 g V排"},
        {"环节": "练习", "内容": "三道计算题"},
    ],
    "板书设计": "浮力 · 阿基米德原理",
    "作业布置": "课后习题 1-3",
}

CTX = dict(level="初中", subject="物理", grade="八年级", duration=45)


class FakeModify:
    """顶掉 LessonPlanGenerator.modify_lesson_plan，可按需注入返回结果。"""

    def __init__(self, result: Any):
        self.result = result
        self.calls: list = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def use_temp_dir():
    tmp = Path(tempfile.mkdtemp(prefix="eduforge-revise-"))
    paths.DATA_DIR = tmp
    return tmp


def install_fake(result: Any) -> FakeModify:
    fake = FakeModify(result)
    lp.lesson_plan_generator.modify_lesson_plan = fake  # type: ignore[method-assign]
    return fake


def seed_v1(lesson_id: str = "lesson-rev") -> str:
    av.save_version(lesson_id, "lesson_plan", dict(BASE_PLAN), note="首次生成：浮力")
    return lesson_id


# ---------------------------------------------------------------------------
def test_guard_before_model() -> None:
    print("\n== 1. 调模型之前的防线（不该浪费额度）==")
    r = asyncio.run(lp.revise_lesson_plan(lesson_id="lesson-none", instruction="换个例子", **CTX))
    check("没有基线版本时直接拒绝", r["success"] is False)
    check("提示语指向'先生成教案'", "先生成教案" in r["message"], f"msg={r['message']!r}")

    lid = seed_v1()
    r = asyncio.run(lp.revise_lesson_plan(lesson_id=lid, instruction="   ", **CTX))
    check("空指令被拒绝", r["success"] is False and "请说明要改什么" in r["message"])

    r = asyncio.run(lp.revise_lesson_plan(lesson_id="../evil", instruction="换个例子", **CTX))
    check("非法课程 id 被拒绝且不崩", r["success"] is False and "读取基线版本失败" in r["message"])


def test_happy_path_saves_version() -> None:
    print("\n== 2. 正常修改 ==")
    lid = seed_v1("lesson-ok")
    modified = dict(BASE_PLAN)
    modified["教学过程设计"] = [
        {"环节": "导入", "内容": "用煮饺子的例子引入浮力"},
        {"环节": "讲授", "内容": "推导 F浮 = ρ液 g V排"},
        {"环节": "练习", "内容": "三道计算题"},
    ]
    fake = install_fake({
        "modified_lesson_plan": modified,
        "change_log": ["导入环节改为生活实例"],
        "ppt_modification_suggestions": ["PPT 第 2 页同步改例子"],
    })

    r = asyncio.run(lp.revise_lesson_plan(
        lesson_id=lid, instruction="导入环节太抽象，换成煮饺子的例子", **CTX))

    check("修改成功", r["success"] is True)
    check("记为 v2", r["version"]["version"] == 2, f"got={r['version']}")
    check("note 记的是教师的原话", r["version"]["note"] == "导入环节太抽象，换成煮饺子的例子")
    check("返回的教案含新导入",
          r["lesson_plan"]["教学过程设计"][0]["内容"] == "用煮饺子的例子引入浮力")
    check("未要求改动的模块原样保留", r["lesson_plan"]["板书设计"] == "浮力 · 阿基米德原理")
    check("把教师指令传给了模型", fake.calls[0]["modification_requirements"].endswith("换成煮饺子的例子"))
    check("基线是从版本链读的（前端不用回传全文）",
          fake.calls[0]["existing_lesson_plan"] == BASE_PLAN)
    check("change_log 被带回", "导入环节改为生活实例" in r["change_log"])
    check("合规闸门结果仍在（只报告不阻断）", "compliance" in r)


def test_empty_result_does_not_overwrite() -> None:
    print("\n== 3. 模型没给出完整教案时绝不能覆盖 ==")
    lid = seed_v1("lesson-empty")
    install_fake({"modified_lesson_plan": {}, "change_log": []})
    before = av.list_versions(lid, "lesson_plan")
    r = asyncio.run(lp.revise_lesson_plan(lesson_id=lid, instruction="整篇重写", **CTX))
    after = av.list_versions(lid, "lesson_plan")

    check("返回失败而不是假装成功", r["success"] is False)
    check("提示语说明原版本未被改动", "原版本未被改动" in r["message"], f"msg={r['message']!r}")
    check("版本链没有新增（没把空内容写成 v2）",
          len(after["versions"]) == len(before["versions"]),
          f"{len(before['versions'])} -> {len(after['versions'])}")
    check("当前版本仍是 v1", after["current"] == 1)
    check("原内容完好无损", av.get_content(lid, "lesson_plan") == BASE_PLAN)

    install_fake({"whatever": "模型这次连 modified_lesson_plan 这个键都没给"})
    r = asyncio.run(lp.revise_lesson_plan(lesson_id=lid, instruction="再试一次", **CTX))
    check("键名不对时同样拒绝", r["success"] is False)
    check("版本号没有被偷偷前进", av.list_versions(lid, "lesson_plan")["current"] == 1)


def test_missing_modules_are_filled_back() -> None:
    print("\n== 4. 模型漏模块时用原文补回（不能让内容凭空消失）==")
    lid = seed_v1("lesson-partial")
    # 模型只回了它改的两个模块
    install_fake({"modified_lesson_plan": {
        "教学目标": ["理解浮力产生的原因（改）"],
        "作业布置": "课后习题 1-5",
    }})
    r = asyncio.run(lp.revise_lesson_plan(lesson_id=lid, instruction="作业加两题", **CTX))

    check("修改仍算成功", r["success"] is True)
    plan = r["lesson_plan"]
    check("模型改到的模块用了新内容", plan["教学目标"] == ["理解浮力产生的原因（改）"])
    check("模型漏掉的模块被补回原文", plan["板书设计"] == "浮力 · 阿基米德原理")
    check("漏掉的教学过程也补回来了", len(plan["教学过程设计"]) == 3)
    check("change_log 如实告知哪些模块是自动保留的",
          any("自动保留未改动的模块" in c for c in r["change_log"]), f"log={r['change_log']}")


def test_revert_after_bad_revision() -> None:
    print("\n== 5. 改坏了能回退 ==")
    lid = seed_v1("lesson-revert")
    bad = dict(BASE_PLAN)
    bad["教学过程设计"] = [{"环节": "导入", "内容": "（模型改坏了，内容很短）"}]
    install_fake({"modified_lesson_plan": bad})
    r = asyncio.run(lp.revise_lesson_plan(lesson_id=lid, instruction="精简导入", **CTX))
    check("已改为 v2", r["version"]["version"] == 2)

    back = av.revert_to(lid, "lesson_plan", 1)
    check("回退产生 v3", back["version"] == 3)
    check("回退后内容回到初版", av.get_content(lid, "lesson_plan") == BASE_PLAN)
    check("三个版本都还在（回退不删历史）",
          len(av.list_versions(lid, "lesson_plan")["versions"]) == 3)


def test_model_exception_is_reported() -> None:
    print("\n== 6. 模型调用失败 ==")
    lid = seed_v1("lesson-err")
    install_fake(RuntimeError("真实模型调用失败"))
    r = asyncio.run(lp.revise_lesson_plan(lesson_id=lid, instruction="随便改改", **CTX))
    check("失败被如实报出（不静默兜底）", r["success"] is False and "教案修改失败" in r["message"])
    check("失败时不产生新版本", av.list_versions(lid, "lesson_plan")["current"] == 1)


def test_generate_full_seeds_v1() -> None:
    print("\n== 7. 生成时把成品落为 v1 ==")
    lid = "lesson-gen"

    lp.lesson_plan_generator.analyze_requirements = lambda **k: {"topic": "浮力"}  # type: ignore
    lp.lesson_plan_generator.generate_outline = lambda x: {"modules": []}  # type: ignore
    lp.lesson_plan_generator.generate_detailed_content = lambda o, r: dict(BASE_PLAN)  # type: ignore
    lp.lesson_plan_generator.validate_compliance = lambda p, l, s: {  # type: ignore
        "corrected_lesson_plan": dict(BASE_PLAN), "validation_report": "ok"}

    gen_kw = dict(level="初中", subject="物理", grade="八年级", topic="浮力",
                  duration=45, requirements="", reference_files=None)
    r = asyncio.run(lp.generate_full_lesson_plan(lesson_id=lid, **gen_kw))
    check("生成成功", r["success"] is True, f"msg={r.get('message')!r}")
    check("返回了版本信息", r.get("version") and r["version"]["version"] == 1)
    check("版本链里确实有了 v1", av.get_content(lid, "lesson_plan") == BASE_PLAN)

    # 存版本失败不能把"生成成功"变成失败
    real_save = av.save_version
    av.save_version = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("磁盘满了"))  # type: ignore
    try:
        r2 = asyncio.run(lp.generate_full_lesson_plan(lesson_id="lesson-x", **gen_kw))
        check("存版本失败不影响生成成功", r2["success"] is True)
        check("失败原因挂在 version_error 上", bool(r2.get("version_error")))
    finally:
        av.save_version = real_save  # type: ignore

    r3 = asyncio.run(lp.generate_full_lesson_plan(**gen_kw))
    check("不给 lesson_id 时行为不变（不存版本）", r3["success"] is True and r3["version"] is None)


# ---------------------------------------------------------------------------
def main() -> int:
    print("=" * 64)
    print("教案「按指令修改」冒烟测试（不调模型）")
    print("=" * 64)
    tmp = use_temp_dir()
    try:
        for fn in (
            test_guard_before_model,
            test_happy_path_saves_version,
            test_empty_result_does_not_overwrite,
            test_missing_modules_are_filled_back,
            test_revert_after_bad_revision,
            test_model_exception_is_reported,
            test_generate_full_seeds_v1,
        ):
            fn()
    finally:
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
