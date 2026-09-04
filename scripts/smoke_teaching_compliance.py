"""教学合规校验器（app/services/teaching_compliance + app/api/teaching_compliance）冒烟测试。

不依赖 TestClient —— 与 scripts/smoke_safety.py 同样的原因（starlette 0.35 与
httpx 0.28 不兼容 TestClient）。这里直接调用服务类与端点函数。

覆盖：
  1. 服务层规则命中（R1~R6 正例 + 反例）
  2. 隐私泄露 R5 的 error / warn 分级
  3. 学段匹配 R4 仅对小学/初中触发，高中不误报
  4. 评分算法（error -25 / warn -8 / info 0）与 passed 判定
  5. 产物类型裁剪：game/animation 不触发 R1/R3
  6. 端点函数 /api/teaching-compliance/check 的返回结构
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.teaching_compliance import (  # noqa: E402
    SEVERITY_ERROR,
    SEVERITY_WARN,
    SEVERITY_INFO,
    flatten_to_text,
    pick_assessment_text,
    run_compliance_gate,
    teaching_compliance_checker,
)
# 端点为 async 函数，单独导入用于结构验证
from app.api import teaching_compliance as tc_api  # noqa: E402

PASS: list = []
FAIL: list = []


def check(name: str, cond: bool, extra: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  {extra}" if extra else ""))


def codes(report) -> set:
    return {i.code for i in report.issues}


def sev_of(report, code):
    for i in report.issues:
        if i.code == code:
            return i.severity
    return None


# ---------------------------------------------------------------------------
# 1. R1 课标依据
# ---------------------------------------------------------------------------
def test_r1_curriculum() -> None:
    print("\n== 1. R1 课标依据 ==")
    # 缺课标 -> warn R1（lesson_plan）
    r = teaching_compliance_checker.check(
        "lesson_plan", "本节课的教学目标是让学生理解浮力原理，安排三个教学环节。",
        {"level": "初中", "subject": "物理", "topic": "浮力"},
    )
    check("缺课标依据 -> R1 warn", "R1" in codes(r) and sev_of(r, "R1") == SEVERITY_WARN)
    # 有课标 -> 不报 R1
    r2 = teaching_compliance_checker.check(
        "lesson_plan",
        "依据《义务教育课程方案（2022 版）》课程标准，本节课对标物理核心素养。",
        {"level": "初中", "subject": "物理", "topic": "浮力"},
    )
    check("含 2022 版课标 -> 不报 R1", "R1" not in codes(r2))


# ---------------------------------------------------------------------------
# 2. R2 核心素养升级
# ---------------------------------------------------------------------------
def test_r2_core_literacy() -> None:
    print("\n== 2. R2 核心素养升级 ==")
    # 旧三维目标、缺核心素养 -> warn R2
    r = teaching_compliance_checker.check(
        "lesson_plan",
        "本节课的三维目标是：知识与技能、过程与方法、情感态度与价值观。",
        {},
    )
    check("旧三维目标 -> R2 warn",
          "R2" in codes(r) and sev_of(r, "R2") == SEVERITY_WARN)
    # 已用核心素养 -> info R2（不报 warn）
    r2 = teaching_compliance_checker.check(
        "lesson_plan",
        "本节课聚焦物理核心素养，培养学生的科学思维与科学探究能力。",
        {},
    )
    check("已用核心素养 -> R2 info 而非 warn",
          sev_of(r2, "R2") == SEVERITY_INFO)
    # 三维 + 核心素养 同时存在 -> 不报 warn（视为已升级）
    r3 = teaching_compliance_checker.check(
        "lesson_plan",
        "围绕核心素养，将原三维目标重构为物理观念、科学思维等维度。",
        {},
    )
    check("三维与核心素养并存 -> 不报 R2 warn",
          sev_of(r3, "R2") != SEVERITY_WARN)


# ---------------------------------------------------------------------------
# 3. R3 教材版本
# ---------------------------------------------------------------------------
def test_r3_textbook() -> None:
    print("\n== 3. R3 教材版本 ==")
    r = teaching_compliance_checker.check(
        "lesson_plan", "本节课讲解浮力的基本概念与计算公式。",
        {"level": "初中", "subject": "物理", "topic": "浮力"},
    )
    check("未标教材版本 -> R3 warn",
          "R3" in codes(r) and sev_of(r, "R3") == SEVERITY_WARN)
    r2 = teaching_compliance_checker.check(
        "lesson_plan",
        "依据人教版八年级下册第十章《浮力》进行教学。",
        {"level": "初中", "subject": "物理", "topic": "浮力"},
    )
    check("标注人教版章节 -> 不报 R3", "R3" not in codes(r2))


# ---------------------------------------------------------------------------
# 4. R4 学段匹配
# ---------------------------------------------------------------------------
def test_r4_stage() -> None:
    print("\n== 4. R4 学段匹配 ==")
    # 小学 + 高考 -> warn
    r = teaching_compliance_checker.check(
        "lesson_plan", "本节课引入高考真题作为拓展。", {"level": "小学"})
    check("小学出现『高考』 -> R4 warn",
          "R4" in codes(r) and sev_of(r, "R4") == SEVERITY_WARN)
    # 初中 + 研究生 -> warn
    r2 = teaching_compliance_checker.check(
        "lesson_plan", "建议学生关注研究生阶段的科研素养。", {"level": "初中"})
    check("初中出现『研究生』 -> R4 warn", "R4" in codes(r2))
    # 高中 + 高考 -> 不误报（R4 只对小学/初中触发）
    r3 = teaching_compliance_checker.check(
        "lesson_plan", "本节课我们研究高考常见题型。", {"level": "高中"})
    check("高中出现『高考』 -> 不误报 R4", "R4" not in codes(r3))
    # 未给 level -> 不触发
    r4 = teaching_compliance_checker.check(
        "lesson_plan", "本节课引入高考真题作为拓展。", {})
    check("未给学段 -> 不触发 R4", "R4" not in codes(r4))


# ---------------------------------------------------------------------------
# 5. R5 隐私泄露（error / warn 分级）
# ---------------------------------------------------------------------------
def test_r5_privacy() -> None:
    print("\n== 5. R5 隐私泄露 ==")
    # 手机号 -> error
    r = teaching_compliance_checker.check(
        "lesson_plan", "请家长王先生 13812345678 到校沟通。", {})
    check("手机号 -> R5 error",
          "R5" in codes(r) and sev_of(r, "R5") == SEVERITY_ERROR)
    # 身份证 -> error
    r2 = teaching_compliance_checker.check(
        "lesson_plan", "该生身份证号为 11010119900307551X。", {})
    check("身份证号 -> R5 error", sev_of(r2, "R5") == SEVERITY_ERROR)
    # 姓名:成绩 -> error
    r3 = teaching_compliance_checker.check(
        "lesson_plan", "本次成绩：张三：85 李四：92 王五：78。", {})
    check("姓名:成绩 -> R5 error", sev_of(r3, "R5") == SEVERITY_ERROR)
    # 邮箱 -> warn（非 error）
    r4 = teaching_compliance_checker.check(
        "lesson_plan", "反馈请发 zhang@school.edu.cn。", {})
    check("邮箱 -> R5 warn（非 error）",
          "R5" in codes(r4) and sev_of(r4, "R5") == SEVERITY_WARN)
    # 无隐私 -> 不报 R5
    r5 = teaching_compliance_checker.check(
        "lesson_plan", "本节课安排小组讨论与随堂练习。", {})
    check("无隐私信息 -> 不报 R5", "R5" not in codes(r5))

    # --- 误报防护：教学内容里的数值标签不能被当成「姓名:成绩」 ---
    # 物理/数学题里「重力：10N」「答案：3」与"姓名:成绩"长得一样，
    # 误报会直接毁掉质检器的可信度，故逐条钉死。
    false_positives = [
        ("物理量带单位", "已知物体重力：10N，浮力：4N，求合力：6N。"),
        ("答案与题号", "答案：3，选项：2，题号：5。"),
        ("页码与课时", "页码：12，课时：2，组号：3。"),
        ("密度带小数", "密度：1.0g/cm3，体积：50cm3。"),
        ("百分比", "及格率：85%，正确率：92%。"),
    ]
    for name, text in false_positives:
        rr = teaching_compliance_checker.check("lesson_plan", text, {})
        hit = [i.message for i in rr.issues if i.code == "R5"]
        check(f"误报防护：{name} 不判为隐私", not hit, f"({hit})")

    # 真实姓名成绩仍必须报出（防止过滤过头）
    rr = teaching_compliance_checker.check(
        "lesson_plan", "本次月考：张三：85，李四：92。", {})
    check("真实姓名成绩仍被检出", any(i.code == "R5" for i in rr.issues))

    # 手机号 + 姓名成绩 同时出现 -> 两个 R5 都应报出（不短路）
    r6 = teaching_compliance_checker.check(
        "lesson_plan", "联系 13812345678。成绩：张三：85 李四：92。", {})
    r5_count = sum(1 for i in r6.issues if i.code == "R5")
    check("手机号+姓名成绩 同时报出 2 条 R5（不短路）",
          r5_count == 2, f"(实际 {r5_count} 条)")
    check("两条 R5 均为 error", all(
        i.severity == SEVERITY_ERROR for i in r6.issues if i.code == "R5"))


# ---------------------------------------------------------------------------
# 6. R6 时长规范
# ---------------------------------------------------------------------------
def test_r6_duration() -> None:
    print("\n== 6. R6 时长规范 ==")
    # PPT 30 页 / 45 分钟 -> 页数偏多 info
    pages = " ".join(f"第{i}页" for i in range(1, 31))
    r = teaching_compliance_checker.check(
        "ppt", pages, {"duration": 45})
    check("PPT 30 页 / 45 分钟 -> R6 info（页数偏多）",
          "R6" in codes(r) and sev_of(r, "R6") == SEVERITY_INFO)
    # 页数适中 -> 不报 R6
    pages2 = " ".join(f"第{i}页" for i in range(1, 13))
    r2 = teaching_compliance_checker.check(
        "ppt", pages2, {"duration": 45})
    check("PPT 12 页 / 45 分钟 -> 不报 R6", "R6" not in codes(r2))
    # 未给课时 -> 不触发 R6
    r3 = teaching_compliance_checker.check("ppt", pages, {})
    check("未给 duration -> 不触发 R6", "R6" not in codes(r3))


# ---------------------------------------------------------------------------
# 6b. R7 行为动词可测量
# ---------------------------------------------------------------------------
def test_r7_measurable_verbs() -> None:
    print("\n== 6b. R7 行为动词可测量 ==")
    # 模糊动词（无法观测、无法评价）-> warn
    r = teaching_compliance_checker.check(
        "lesson_plan", "教学目标",
        {"objectives_text": "了解浮力的概念，理解阿基米德原理，掌握物体的浮沉条件"})
    check("教学目标含模糊动词 -> 报 R7", "R7" in codes(r), f"({codes(r)})")
    check("R7 为 warn 而非 error", sev_of(r, "R7") == SEVERITY_WARN)
    msg = next((i.message for i in r.issues if i.code == "R7"), "")
    check("R7 提示点名具体动词", ("了解" in msg or "理解" in msg), f"({msg})")

    # 可测量动词 -> 不报
    r2 = teaching_compliance_checker.check(
        "lesson_plan", "教学目标",
        {"objectives_text": "能说出阿基米德原理，能用公式计算浮力，能设计实验验证"})
    check("可测量动词 -> 不报 R7", "R7" not in codes(r2))

    # 未提供教学目标文本 -> 绝不误报（宁可不报，也不在全文里瞎猜哪段是目标）
    r3 = teaching_compliance_checker.check(
        "lesson_plan", "了解浮力，掌握原理，理解概念", {})
    check("未提供 objectives_text -> 不报 R7（防误报）", "R7" not in codes(r3))

    # --- R8 教学评一致性：有目标却无检测 ---
    r4 = teaching_compliance_checker.check(
        "lesson_plan", "教学目标",
        {"objectives_text": "能说出阿基米德原理", "assessment_text": ""})
    check("有目标但无检测 -> 报 R8", "R8" in codes(r4), f"({codes(r4)})")
    check("R8 为 warn 而非 error", sev_of(r4, "R8") == SEVERITY_WARN)

    # 有检测 -> 不报
    r5 = teaching_compliance_checker.check(
        "lesson_plan", "教学目标",
        {"objectives_text": "能说出阿基米德原理",
         "assessment_text": "当堂检测：请计算铁块浸没时的浮力"})
    check("有检测设计 -> 不报 R8", "R8" not in codes(r5))

    # 连目标都没有 -> 不报（没目标谈不上"目标无法验证"）
    r6 = teaching_compliance_checker.check(
        "lesson_plan", "教学过程", {"assessment_text": ""})
    check("无教学目标 -> 不报 R8（防误报）", "R8" not in codes(r6))

    # --- pick_assessment_text：模块名不固定时应能取到 ---
    lp_a = {"评价设计": {"当堂检测": "计算浮力"}}
    lp_b = {"当堂检测": "计算浮力"}
    lp_c = {"教学目标": "能说出原理"}      # 完全没有评价模块
    check("pick_assessment_text 命中「评价设计」",
          pick_assessment_text(lp_a) != "")
    check("pick_assessment_text 命中「当堂检测」",
          pick_assessment_text(lp_b) != "")
    check("pick_assessment_text 无评价模块时返回空",
          pick_assessment_text(lp_c) == "")


# ---------------------------------------------------------------------------
# 7. 评分与 passed
# ---------------------------------------------------------------------------
def test_score_and_pass() -> None:
    print("\n== 7. 评分 / passed ==")
    # 干净教案（有课标+核心素养+教材版本，高中，无隐私）-> 100 分 passed
    clean = ("依据《义务教育课程方案（2022 版）》课程标准，"
             "聚焦物理核心素养（物理观念、科学思维）。"
             "使用人教版高中物理必修一第二章《匀变速直线运动》。")
    r = teaching_compliance_checker.check(
        "lesson_plan", clean, {"level": "高中", "subject": "物理", "topic": "运动学"})
    check("干净教案 -> 100 分", r.score == 100, f"(实际 {r.score})")
    check("干净教案 -> passed=True", r.passed is True)
    check("干净教案 -> 仅 R2 info", codes(r) == {"R2"} and sev_of(r, "R2") == SEVERITY_INFO)

    # 含手机号（但其余合规）-> passed=False，仅扣 25（其余满分）
    r2 = teaching_compliance_checker.check(
        "lesson_plan",
        "依据《义务教育课程方案（2022 版）》课程标准，使用人教版高中物理必修一，"
        "聚焦物理核心素养。联系电话 13812345678。",
        {"level": "高中"},
    )
    check("含隐私 -> passed=False", r2.passed is False)
    check("含 error 且其余合规 -> 扣 25 分（75）",
          r2.score == 75, f"(实际 {r2.score}, 命中 {codes(r2)})")

    # 仅 warn -> passed=True，扣 8
    r3 = teaching_compliance_checker.check(
        "lesson_plan", "本节课讲解浮力。", {"level": "初中", "topic": "浮力"})
    # 缺课标(R1 warn) + 缺教材版本(R3 warn) = -16，但可能还有别的
    check("warn 不阻断 passed", r3.passed is True)
    check("warn 扣分到位（>=8 且 <100）",
          8 <= (100 - r3.score) < 100, f"(扣 {100 - r3.score})")

    # 空内容 -> R0 warn，passed 且 score 92
    r4 = teaching_compliance_checker.check("lesson_plan", "", {})
    check("空内容 -> R0 warn", "R0" in codes(r4))
    check("空内容 -> passed=True", r4.passed is True)


# ---------------------------------------------------------------------------
# 8. 产物类型裁剪
# ---------------------------------------------------------------------------
def test_type_trimming() -> None:
    print("\n== 8. 产物类型裁剪 ==")
    # game 不应因缺课标/教材版本而报 R1/R3
    r = teaching_compliance_checker.check(
        "game", "这是一个记忆翻牌游戏，点击两张牌进行配对。", {})
    check("game 不触发 R1", "R1" not in codes(r))
    check("game 不触发 R3", "R3" not in codes(r))
    # 但 game 仍需查隐私
    r2 = teaching_compliance_checker.check(
        "game", "玩家手机号 13812345678 用于排行榜。", {})
    check("game 仍触发 R5 隐私", sev_of(r2, "R5") == SEVERITY_ERROR)


# ---------------------------------------------------------------------------
# 8b. 出厂质检闸门（生成流程接入用）
# ---------------------------------------------------------------------------
def test_compliance_gate() -> None:
    print("\n== 8b. 出厂质检闸门（run_compliance_gate / flatten_to_text）==")
    # --- flatten_to_text ---
    html = ("<html><script>var a=1;</script><style>.x{color:red}</style>"
            "<p>阿基米德原理 F_浮=ρ_液gV_排</p></html>")
    t = flatten_to_text({
        "title": "浮力", "html_content": html,
        "task_id": "abc-123", "pptx_path": "/data/a.pptx", "files": {"pptx": "a.pptx"},
    })
    check("HTML 的 script/style 被剥离", "var a" not in t and "color:red" not in t)
    check("HTML 正文被保留", "阿基米德原理" in t)
    check("普通字段被保留", "浮力" in t)
    check("路径/ID 类字段被跳过",
          "abc-123" not in t and "/data/a.pptx" not in t and "a.pptx" not in t)

    # 长文本截断，防止大 HTML 拖慢正则
    t2 = flatten_to_text({"c": "教学内容" * 5000})
    check("超长文本被截断（<=12000）", len(t2) <= 12000, f"(实际 {len(t2)})")

    # --- 闸门：正常路径 ---
    g = run_compliance_gate("lesson_plan", {"content": "联系 13812345678。"},
                            {"level": "小学"})
    check("闸门 enabled=True", g.get("enabled") is True)
    check("闸门报出隐私 -> passed=False", g.get("passed") is False)
    check("闸门返回 issues 结构", isinstance(g.get("issues"), list) and g["issues"])
    check("闸门返回 suggestions", isinstance(g.get("suggestions"), list))

    # --- 闸门：只报告、绝不抛异常（不能给生成引入新失败模式）---
    for bad in (None, 12345, "abc", [1, 2, 3]):
        r = run_compliance_gate("lesson_plan", bad, {})
        check(f"闸门对异常输入 {bad!r} 不抛异常",
              isinstance(r, dict) and "enabled" in r)

    # 循环引用也不应让生成失败
    cyc: dict = {}
    cyc["self"] = cyc
    r_cyc = run_compliance_gate("lesson_plan", cyc, {})
    check("闸门对循环引用不崩溃", isinstance(r_cyc, dict))

    # --- 闸门：page_count 优先于正则估算 ---
    g1 = run_compliance_gate("ppt", {"content": "教学课件"},
                             {"duration": 45, "page_count": 30})
    has_r6_30 = any(i["code"] == "R6" and "30 页" in i["message"]
                    for i in g1.get("issues", []))
    check("R6 使用真实页数（30 页）", has_r6_30,
          f"({[i['message'] for i in g1.get('issues', []) if i['code']=='R6']})")
    g2 = run_compliance_gate("ppt", {"content": "教学课件"},
                             {"duration": 45, "page_count": 10})
    has_r6_10 = any(i["code"] == "R6" for i in g2.get("issues", []))
    check("R6 页数未超阈值不报（10 页）", not has_r6_10)

    # --- 闸门：总开关 ---
    os.environ["EDUFORGE_COMPLIANCE_GATE"] = "0"
    g_off = run_compliance_gate("lesson_plan", {"content": "测试"}, {})
    check("开关关闭时不质检（enabled=False）", g_off.get("enabled") is False)
    os.environ["EDUFORGE_COMPLIANCE_GATE"] = "1"


# ---------------------------------------------------------------------------
# 9. 端点函数返回结构
# ---------------------------------------------------------------------------
async def _call_endpoint():
    return await tc_api.check_teaching_compliance(
        artifact_type="lesson_plan",
        content="联系电话 13812345678，成绩：张三：85。",
        meta={"level": "小学", "subject": "语文", "topic": "作文"},
    )


def test_endpoint_structure() -> None:
    print("\n== 9. 端点函数 /api/teaching-compliance/check ==")
    check("router 已定义且挂载路径含 teaching-compliance/check",
          "/teaching-compliance/check" in [r.path for r in tc_api.router.routes])
    out = asyncio.run(_call_endpoint())
    check("端点返回 success=True", out.get("success") is True)
    rep = out.get("report") or {}
    check("report 含 artifact_type", rep.get("artifact_type") == "lesson_plan")
    check("report 含 score（int）", isinstance(rep.get("score"), int))
    check("report 含 passed（bool）", isinstance(rep.get("passed"), bool))
    check("report 含 issues 列表", isinstance(rep.get("issues"), list))
    check("report 含 suggestions 列表", isinstance(rep.get("suggestions"), list))
    # 手机号 + 姓名成绩 均为 error -> passed=False
    check("端点：含隐私 -> passed=False", rep.get("passed") is False)
    codes_remote = {i.get("code") for i in rep.get("issues", [])}
    check("端点：报出 R5 隐私", "R5" in codes_remote, f"({codes_remote})")


def main() -> int:
    print("教学合规校验器冒烟测试")
    test_r1_curriculum()
    test_r2_core_literacy()
    test_r3_textbook()
    test_r4_stage()
    test_r5_privacy()
    test_r6_duration()
    test_r7_measurable_verbs()
    test_score_and_pass()
    test_type_trimming()
    test_compliance_gate()
    test_endpoint_structure()

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
