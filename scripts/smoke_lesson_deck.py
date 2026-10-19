"""课件契约与校验器的回归测试。

钉死两件事：
1. **合格样例必须判合格**（12 份黄金样例不能有误杀）
2. **不合格的必须拦住** —— 尤其是我们**自己此前真实产出过**的那几类：
   - 有占位符（授课教师：XXX / 教材PXX页）
   - 缺教学闭环（只有知识点堆砌，没有练习/小结/作业）
   - 练习只出题不给答案
   - 只有活动名没有活动内容（"小组讨论"但没有讨论题/分工/反馈）

还有一个必须钉的：**不得误杀** —— 英语/语文题里的短下划线是合法填空线，
不是待填占位。误报一多，这个校验就没人信了。

运行：PYTHONPATH=backend uv run --project backend python scripts/smoke_lesson_deck.py
"""

from __future__ import annotations

import copy
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

PASS, FAIL = [], []


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  {extra}" if extra else ""))


def main() -> int:
    print("=" * 64)
    print("课件契约与校验 —— 行为测试")
    print("=" * 64)

    from app.services.lesson_deck import (load_golden, validate_deck, find_golden,
                                          find_placeholders, PAGE_SPEC, CLOSURE_STAGES)

    # ---- 1. 黄金样例全部合格 ----
    print("\n== 1. 12 份黄金样例必须判合格（不能有误杀） ==")
    gs = load_golden()
    check("黄金样例已入库", len(gs) == 12, f"{len(gs)} 份")
    bad = []
    for d in gs:
        r = validate_deck(d)
        if not r["ok"]:
            bad.append(f"{d.get('subject')}/{d.get('title')}: {r['errors'][:1]}")
    check("全部合格", not bad, "; ".join(bad[:2]))

    # ---- 2. 反例：占位符必须拦住 ----
    print("\n== 2. 反例：占位符（我们自己真实产出过） ==")
    base = copy.deepcopy(gs[0])
    for ph_text in ["授课教师：XXX", "教材PXX页第3题", "（请根据实际情况补充）",
                    "此处插入图片", "示例内容", "老师自行设计"]:
        d = copy.deepcopy(base)
        d["slides"][1]["items"] = [ph_text, "第二条"]
        r = validate_deck(d)
        check(f"拦住「{ph_text}」", not r["ok"] and any("占位符" in e for e in r["errors"]))

    # 长串下划线 = 留白待填，要拦
    d = copy.deepcopy(base)
    d["slides"][1]["items"] = ["授课教师 ________", "第二条"]
    check("拦住长下划线（留白待填）", not validate_deck(d)["ok"])

    # ---- 3. 不得误杀：题目里的短下划线 ----
    print("\n== 3. 不得误杀：题目里的合法填空线 ==")
    check("find_placeholders 在正常文本放行短下划线",
          find_placeholders("My mother is in the ____.", in_question=True) == [])
    check("但题目里的 TODO 仍要抓",
          find_placeholders("翻译：TODO", in_question=True) != [])
    d = copy.deepcopy(base)
    ex_idx = [i for i, s in enumerate(d["slides"]) if s.get("type") == "exercise"]
    if ex_idx:
        d["slides"][ex_idx[0]]["items"] = [{"q": "My mother is in the ____.", "a": "kitchen"}]
        r = validate_deck(d)
        check("含填空线的练习页仍合格", r["ok"], str(r["errors"][:1]))

    # ---- 4. 反例：缺教学闭环 ----
    print("\n== 4. 反例：缺教学闭环 ==")
    for drop in ("exercise", "summary", "homework"):
        d = copy.deepcopy(base)
        d["slides"] = [s for s in d["slides"] if s.get("type") != drop]
        r = validate_deck(d)
        check(f"去掉 {drop} 页 → 判不合格", not r["ok"], f"缺{r['missing_stages']}")

    # ---- 5. 反例：练习只出题不给答案 ----
    print("\n== 5. 反例：练习必须有答案 ==")
    d = copy.deepcopy(base)
    ex = [s for s in d["slides"] if s.get("type") == "exercise"]
    if ex:
        ex[0]["items"] = [{"q": "物体浸没后浮力是否变化？"}]
        r = validate_deck(d)
        check("练习缺答案 → 拦住", any("缺少答案" in e for e in r["errors"]))

    # ---- 6. 反例：只有活动名没有活动内容 ----
    print("\n== 6. 反例：只给活动名不给内容 ==")
    d = copy.deepcopy(base)
    act = [s for s in d["slides"] if s.get("type") == "activity"]
    if act:
        act[0]["steps"] = []          # 只有"小组讨论"，没有讨论题/分工/反馈
        r = validate_deck(d)
        check("活动 steps 为空 → 拦住", any("为空列表" in e for e in r["errors"]))
    d2 = copy.deepcopy(base)
    d2["slides"] = [{"type": "activity", "title": "小组讨论"}]   # 只有名字
    check("只有活动名 → 拦住", not validate_deck(d2)["ok"])

    # ---- 7. 契约完整性 ----
    print("\n== 7. 契约完整性 ==")
    check("12 种页面类型齐全", len(PAGE_SPEC) == 12, str(sorted(PAGE_SPEC)))
    check("闭环 6 段齐全", len(CLOSURE_STAGES) == 6)
    check("未知类型会被拦", not validate_deck(
        {"meta": {"topic": "x", "subject": "物理"},
         "slides": [{"type": "不存在的类型"}]})["ok"])

    # ---- 8. 查样例 ----
    print("\n== 8. 黄金样例检索 ==")
    check("按学科+课题命中", (find_golden("物理", "浮力") or {}).get("title") == "浮力")
    check("学科不符不命中", find_golden("语文", "浮力") is None)

    print("\n" + "=" * 64)
    print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    if FAIL:
        for n in FAIL:
            print(f"  - {n}")
    print("=" * 64)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
