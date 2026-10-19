"""教材索引的回归测试。

钉死三条：
1. **查得到要定位准**（章/节/页码）
2. **查不到必须返回 None**（绝不能编造章节号 —— 这是幻觉，比不提供更有害）
3. 索引里**不能有教材正文**（版权红线：版权归出版社，只存目录用于定位）

运行：PYTHONPATH=backend uv run --project backend python scripts/smoke_textbook_index.py
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
    print("教材索引 —— 行为测试")
    print("=" * 64)

    from app.services import textbook_index as ti

    books = ti.available_books()
    print(f"\n（本地已建索引 {len(books)} 本："
          f"{', '.join(f'{b[chr(39) if False else 'subject'] or '?'}{b.get('grade') or ''}' for b in books)}）")

    # ---- 1. 索引文件本身：结构合规 ----
    print("\n== 1. 索引合规：只有目录，没有正文 ==")
    idx_path = os.path.join(ROOT, "knowledge_base", "textbooks", "index.json")
    if os.path.exists(idx_path):
        with open(idx_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        check("索引文件是合法 JSON", isinstance(raw, dict))
        check("索引声明不含正文", "正文" in json.dumps(raw.get("note", ""), ensure_ascii=False))
        # 正文检测：任何一条标题都不该过长（长段落 = 正文被误存）
        longest = 0
        for b in raw.get("books", []):
            for u in b.get("units", []):
                longest = max(longest, len(u.get("title", "")))
                for s in u.get("sections", []):
                    longest = max(longest, len(s.get("title", "")))
        check("目录条目都是短标题（无正文混入）", longest <= 60, f"最长 {longest} 字")
    else:
        print("  （索引文件不存在，跳过结构检查）")

    # ---- 2. 查得到 → 定位准 ----
    print("\n== 2. 有教材时要定位准 ==")
    for subject, grade, topic, want in [
        ("物理", "八年级", "质量", "质量"),
        ("物理", "八年级", "光的反射", "光的反射"),
        ("物理", "八年级", "光的折射", "光的折射"),
    ]:
        r = ti.lookup(subject, grade, topic)
        ok = r is not None and want in (r.get("section") or r.get("chapter") or "")
        check(f"{subject}{grade}「{topic}」→ 定位到 {want}", ok,
              f"{r.get('chapter')} {r.get('section')} p{r.get('page')}" if r else "未命中")

    # ---- 3. 查不到 → 必须 None（核心：不许编造） ----
    print("\n== 3. 没教材时必须返回 None，不得编造章节号 ==")
    for subject, grade, topic in [
        ("物理", "八年级", "浮力"),          # 在下册，本地只有上册
        ("生物", "七年级", "细胞的结构"),     # 本地无生物教材
        ("化学", "九年级", "质量守恒定律"),   # 本地无化学教材
    ]:
        r = ti.lookup(subject, grade, topic)
        check(f"{subject}「{topic}」→ None（降级）", r is None)

    # 降级文案必须明确要求"不要编造"
    msg = ti.describe("物理", "八年级", "浮力")
    check("降级提示里明确禁止编造章节号", "不要编造" in msg and "教材章节号" in msg, msg[:52])
    check("降级提示里说明原因", "没有" in msg)

    # ---- 4. 年级别名 ----
    print("\n== 4. 年级别名与边界 ==")
    check("初二 = 八年级", ti.lookup("物理", "初二", "质量") is not None)
    check("空主题 → None", ti.lookup("物理", "八年级", "") is None)
    check("空学科 → None", ti.lookup("", "八年级", "浮力") is None)
    check("全空 → None", ti.lookup("", "", "") is None)
    check("无意义主题不误命中", ti.lookup("物理", "八年级", "量子纠缠") is None)

    print("\n" + "=" * 64)
    print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    if FAIL:
        for n in FAIL:
            print(f"  - {n}")
    print("=" * 64)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
