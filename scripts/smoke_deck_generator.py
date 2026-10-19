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


    # ---- 8. 接入层：契约模式的降级（关键：不能弄坏原有流程） ----
    print("\n== 8. 接入层降级 ==")
    from app.api.ppt import _try_deck_mode, _infer_band

    check("学段推断：八年级→初中", _infer_band("八年级", "物理") == "初中")
    check("学段推断：三年级→小学", _infer_band("三年级", "数学") == "小学")
    check("学段推断：高一→高中", _infer_band("高一", "数学") == "高中")

    class _T:
        progress = 0
        status = ""
        result = None

    # 8.1 命中黄金样例 → 走契约模式
    t1 = _T()
    ok1 = _try_deck_mode(t1, "smoke01", "浮力", 45, "八年级", "物理", "蓝色系", "标准", [], "")
    check("命中黄金样例 → 交付", ok1 is True)
    if ok1:
        r1 = t1.result
        check("结果含 pptx 文件名", bool(r1.get("files", {}).get("pptx")))
        check("结果含 task_dir", bool(r1.get("task_dir")))
        check("标记 deck_mode", r1.get("deck_mode") is True)
        check("带合规结果（不阻断）", isinstance(r1.get("compliance"), dict))
        check("带溯源 provenance",
              "provenance" in (r1["ppt_content"]["metadata"] or {}))

    # 8.2 生成的稿子不合格 → 必须降级（不能硬交付）
    orig_generate = DG.generate
    orig_golden = DG.generate_from_golden
    DG.generate_from_golden = lambda s, tp: None
    DG.generate = lambda *a, **k: {"meta": {"subject": "物理", "topic": "浮力"},
                                   "slides": [{"type": "cover"}, {"type": "end"}]}
    t2 = _T()
    try:
        check("不合格稿 → 降级（不交付）",
              _try_deck_mode(t2, "smoke02", "浮力", 45, "八年级", "物理", "蓝色系", "标准", [], "") is False)
    finally:
        DG.generate = orig_generate
        DG.generate_from_golden = orig_golden

    # 8.3 生成器抛异常 → 必须降级，不能把异常抛给调用方
    orig2 = DG.generate
    DG.generate_from_golden = lambda s, tp: None
    def _boom(*a, **k):
        raise RuntimeError("模型挂了")
    DG.generate = _boom
    t3 = _T()
    try:
        check("生成器异常 → 静默降级",
              _try_deck_mode(t3, "smoke03", "浮力", 45, "八年级", "物理", "蓝色系", "标准", [], "") is False)
    finally:
        DG.generate = orig2
        DG.generate_from_golden = orig_golden

    # 8.4 开关可关
    import os as _os
    _os.environ["EDUFORGE_PPT_DECK_MODE"] = "off"
    t4 = _T()
    try:
        check("开关关闭 → 不走契约模式",
              _try_deck_mode(t4, "smoke04", "浮力", 45, "八年级", "物理", "蓝色系", "标准", [], "") is False)
    finally:
        _os.environ.pop("EDUFORGE_PPT_DECK_MODE", None)

    print("\n" + "=" * 64)
    print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    if FAIL:
        for x in FAIL:
            print(f"  - {x}")
    print("=" * 64)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
