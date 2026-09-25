"""课程知识上下文的冒烟测试（真检索 + 注入假检索器，秒级）。

为什么必须有
------------
四路生成（教案 / PPT / 动画 / 游戏）此前**完全不查知识库**，
于是同一节课能给出四套互不一致的说法：教案里的难点、PPT 里的表述、
动画与游戏里的知识点各说各的。教师看到的是"一个系统给了四个版本"。

这个测试钉三件事：
  1. 能真的检索到内容，并且**带溯源**（教师能查依据）；
  2. 检索挂了**不阻断生成** —— 生成不该因为检索抖动而失败；
  3. 四路都调用同一个 `build_course_context`（静态校验），
     少接一路就会红 —— 这类漏接不会报错，只会让那一路悄悄退化。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.course_knowledge import (  # noqa: E402
    CourseKnowledge, append_to_requirements, build_course_context, normalize_subject,
)

PASS: list = []
FAIL: list = []


def check(name: str, cond: bool, extra: str = "") -> None:
    """extra 只在失败时打印 —— 通过时打出来会被误读成告警。"""
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  {extra}" if (extra and not cond) else ""))


# ---------------------------------------------------------------------------
class BrokenRetriever:
    """模拟检索器整体不可用（模型没下载、索引损坏）。"""

    def retrieve(self, *a, **kw):
        raise RuntimeError("embedding 不可用")


class EmptyRetriever:
    """模拟"知识库里没有"（拒答）。"""

    class _Res:
        refused = True
        hits = []

    def retrieve(self, *a, **kw):
        return self._Res()


class RecordingRetriever:
    """记录传进来的 filters，用于验证过滤确实生效。"""

    class _Hit:
        def __init__(self, i):
            self.chunk_id = f"c{i}"
            self.text = f"片段{i}"
            self.raw_text = f"片段{i}正文"
            self.source = f"文档{i}"
            self.heading_path = f"节{i}"
            self.score = 0.9

    class _Res:
        def __init__(self, n):
            self.refused = n == 0
            self.hits = [RecordingRetriever._Hit(i) for i in range(n)]

    def __init__(self, n=2):
        self.calls = []
        self.n = n

    def retrieve(self, query, top_k=5, filters=None, enable_rerank=True, **kw):
        self.calls.append({"query": query, "filters": filters, "top_k": top_k})
        return self._Res(self.n)


print("\n=== 1. 学科名归一化（动画/游戏传英文 key，教案传中文）===")
for raw, want in (("physics", "物理"), ("物理", "物理"), ("初中物理", "物理"),
                  ("mathematics", "数学"), ("general", ""), ("", ""), (None, "")):
    got = normalize_subject(raw)
    check(f"normalize_subject({raw!r}) → {want!r}", got == want, f"实得 {got!r}")

print("\n=== 2. 真检索：能拿到内容且带溯源 ===")
k = build_course_context(topic="浮力", subject="物理", grade="八年级", kind="lesson_plan")
check("非空", not k.empty, f"{len(k.text)} 字")
check("带引用", len(k.citations) >= 2, str(len(k.citations)))
check("引用里有来源与标题路径",
      all(c.get("source") for c in k.citations))
check("内容来自物理篇", any("物理" in (c.get("source") or "") for c in k.citations))
check("文本里有明确的知识块标记", "【课程知识参考" in k.text)

print("\n=== 3. 检索不可用 → 不阻断，返回空 ===")
k2 = build_course_context(topic="浮力", subject="物理", retriever=BrokenRetriever())
check("异常被吞掉，返回空上下文", k2.empty and k2.text == "")
check("空上下文不会拼出脏文本", append_to_requirements("原需求", k2) == "原需求")

print("\n=== 4. 知识库没有 → 不阻断，返回空 ===")
k3 = build_course_context(topic="浮力", subject="物理", retriever=EmptyRetriever())
check("拒答时返回空", k3.empty)

print("\n=== 5. 过滤确实生效（按学科过滤；查不到会退回不过滤）===")
r = RecordingRetriever(n=3)
k4 = build_course_context(topic="浮力", subject="物理", kind="lesson_plan", retriever=r)
check("第一路查询带了 subject 过滤",
      r.calls and r.calls[0]["filters"] == {"subject": "物理"}, str(r.calls[0]["filters"]))
check("教案/课件第二路带 type=教学法 过滤",
      any(c["filters"] == {"type": "教学法"} for c in r.calls), str([c["filters"] for c in r.calls]))

r2 = RecordingRetriever(n=0)
k5 = build_course_context(topic="浮力", subject="物理", kind="lesson_plan", retriever=r2)
check("过滤后没结果 → 退回不过滤再查一次",
      any(c["filters"] is None for c in r2.calls),
      str([c["filters"] for c in r2.calls]))

print("\n=== 6. 动画/游戏不需要 type=教学法 过滤 ===")
r3 = RecordingRetriever(n=2)
build_course_context(topic="浮力", subject="physics", kind="animation", retriever=r3)
check("英文学科 key 也被归一成中文后过滤",
      r3.calls[0]["filters"] == {"subject": "物理"}, str(r3.calls[0]["filters"]))
check("动画不带 type=教学法 过滤",
      all(c["filters"] != {"type": "教学法"} for c in r3.calls))

print("\n=== 7. 边界输入 ===")
check("空主题直接返回空", build_course_context(topic="").empty)
check("None 主题直接返回空", build_course_context(topic=None).empty)
check("只有主题也能查", not build_course_context(topic="浮力").empty)
check("拼接函数：原需求为空时不留多余空行",
      append_to_requirements("", k) == k.text)
check("拼接函数：原需求保留",
      append_to_requirements("重点讲实验", k).startswith("重点讲实验"))
check("max_chars 生效（不会无限长）",
      len(build_course_context(topic="浮力", subject="物理", max_chars=300).text) < 900)

print("\n=== 8. 静态：四路都必须调用同一个入口 ===")
# 少接一路不会报错，只会让那一路悄悄退化成"不查知识库"，所以必须静态钉住
targets = {
    "教案": ROOT / "backend" / "app" / "api" / "lesson_plan.py",
    "PPT": ROOT / "backend" / "app" / "api" / "ppt.py",
    "动画+游戏": ROOT / "backend" / "app" / "api" / "courseware.py",
}
for name, path in targets.items():
    src = path.read_text(encoding="utf-8")
    check(f"{name} 调用了 build_course_context",
          "build_course_context" in src and "course_knowledge" in src)
# 且不能有人另起炉灶直接调 retriever
for name, path in targets.items():
    src = path.read_text(encoding="utf-8")
    check(f"{name} 没有绕过统一入口直接调检索器",
          "get_retriever()" not in src, "发现直连")

print(f"\n通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
if FAIL:
    print("失败项：" + "、".join(FAIL))
    sys.exit(1)
