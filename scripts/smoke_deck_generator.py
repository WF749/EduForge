"""课件生成器的回归测试（注入假 LLM，绝不真调接口烧额度）。

钉死的几条：
1. **不合格要打回重做**，而且要把**具体问题**回传给模型（不是笼统"重做"）
2. **有界自主**：重做有上限，超过就如实标注未通过，不能无限循环
3. **溯源**：每份课件都要带 provenance（教材依据 / 生成依据 / 轮次 / 未通过项）
4. JSON 解析要容错（模型经常包 ```json 或加前后说明）
5. 任何异常都不能让调用方崩

运行：PYTHONPATH=backend uv run --project backend python scripts/smoke_deck_generator.py
"""

from __future__ import annotations

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
    print("课件生成器 —— 行为测试（假 LLM）")
    print("=" * 64)

    from app.services import deck_generator as DG
    from app.services.lesson_deck import validate_deck

    golden = json.load(open(os.path.join(ROOT, "knowledge_base", "golden_decks", "decks.json"),
                            encoding="utf-8"))["decks"]
    good = golden[6]   # 初中物理 浮力

    # ---- 1. 合格稿一次通过 ----
    print("\n== 1. 合格稿一次通过 ==")
    n = {"c": 0}

    def caller_ok(prompt):
        n["c"] += 1
        return json.dumps(good, ensure_ascii=False)

    d = DG.generate("物理", "浮力", grade="八年级", band="初中", caller=caller_ok)
    check("返回结果非空", d is not None)
    check("只调用 1 轮", n["c"] == 1, f"实际 {n['c']}")
    check("provenance 存在", isinstance((d or {}).get("provenance"), dict))
    check("标注已通过校验", (d or {})["provenance"].get("validated") is True)

    # ---- 2. 坏稿被打回重做，且问题回传 ----
    print("\n== 2. 不合格要打回重做，且把具体问题回传 ==")
    bad = {"meta": {"subject": "物理", "topic": "浮力", "grade": "八年级", "band": "初中"},
           "slides": [{"type": "cover"},
                      {"type": "objectives", "items": [{"text": "会测量浮力"}]},
                      {"type": "points", "title": "导入", "items": ["请填写现象"]},
                      {"type": "end"}]}
    seen_prompts = []
    nn = {"c": 0}

    def caller_fix(prompt):
        nn["c"] += 1
        seen_prompts.append(prompt)
        return json.dumps(bad, ensure_ascii=False) if nn["c"] == 1 else json.dumps(good, ensure_ascii=False)

    d2 = DG.generate("物理", "浮力", grade="八年级", band="初中", caller=caller_fix)
    check("调用了第 2 轮", nn["c"] == 2, f"实际 {nn['c']}")
    check("最终结果合格", d2 and validate_deck(d2)["ok"])
    # 第 2 轮 prompt 里必须带上第 1 轮的具体错误
    second = seen_prompts[1] if len(seen_prompts) > 1 else ""
    check("回传了具体错误（占位符）", "占位符" in second)
    check("回传了具体错误（闭环）", "闭环" in second or "缺失" in second)

    # ---- 3. 有界自主：重做有上限 ----
    print("\n== 3. 有界自主：不能无限重做 ==")
    cnt = {"c": 0}

    def caller_always_bad(prompt):
        cnt["c"] += 1
        return json.dumps(bad, ensure_ascii=False)

    d3 = DG.generate("物理", "浮力", grade="八年级", band="初中",
                     max_rounds=3, caller=caller_always_bad)
    check("轮次不超过上限", cnt["c"] <= 3, f"实际 {cnt['c']}")
    check("如实标注未通过", d3 and d3["provenance"].get("validated") is False)
    check("保留未通过项（可追溯）", bool(d3 and d3["provenance"].get("issues")))

    # ---- 4. JSON 容错 ----
    print("\n== 4. JSON 解析容错 ==")
    for wrap in ["```json\n{}\n```", "好的，这是课件：\n{}\n希望对你有帮助"]:
        def c(p, w=wrap):
            return w.replace("{}", json.dumps(good, ensure_ascii=False))
        dd = DG.generate("物理", "浮力", grade="八年级", band="初中", caller=c)
        check(f"能解析 {wrap[:12]}… 包裹的输出", dd is not None and dd.get("slides"))

    def caller_junk(p):
        return "我不是 JSON"

    check("垃圾输出不崩（返回 None 或标注问题）",
          DG.generate("物理", "浮力", caller=caller_junk) is None)

    # ---- 5. 异常不崩 ----
    print("\n== 5. 异常兜底 ==")

    def boom(p):
        raise RuntimeError("模型挂了")

    check("LLM 抛异常 → 返回 None，不向上抛",
          DG.generate("物理", "浮力", caller=boom) is None)

    # ---- 6. 黄金样例复用（零成本） ----
    print("\n== 6. 内置黄金样例复用 ==")
    g = DG.generate_from_golden("物理", "浮力")
    check("命中内置样例", g is not None and g["meta"]["topic"] == "浮力")
    check("标注来源为 golden_deck", g and g["provenance"]["generator"] == "golden_deck")
    check("未命中返回 None", DG.generate_from_golden("物理", "不存在的课题") is None)

    # ---- 7. 溯源内容 ----
    print("\n== 7. 溯源信息 ==")
    g2 = DG.generate_from_golden("物理", "浮力")
    pv = g2["provenance"]
    check("有教材依据字段", "textbook" in pv)
    check("标注是否有教材支撑", isinstance(pv.get("has_textbook"), bool))
    check("浮力无教材时明确禁止编造",
          ("没有" in pv["textbook"] and "不要编造" in pv["textbook"]) or pv["has_textbook"])

    print("\n" + "=" * 64)
    print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    if FAIL:
        for x in FAIL:
            print(f"  - {x}")
    print("=" * 64)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
