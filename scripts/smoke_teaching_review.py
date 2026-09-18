"""可选模型复查的冒烟测试（**注入假 LLM，零模型额度**）。

存在的理由：这条路径默认关闭，所以**平时没人会触发它** ——
正是最容易腐化成死代码的那种功能（上一个这么死掉的是 content_version_manager）。
不开开关就叫不醒它，所以这里直接打开开关 + 注入假 LLM 把整条链路跑一遍。

钉死四件事：
  1. 默认必须关（擅自开会在每次生成时多花一次模型调用）；
  2. 只报告：不改写内容、异常一律吞掉、绝不把生成打回失败；
  3. 模型返回的字段名不是枚举，缺字段补空、查不到原样保留、解析不出也不丢；
  4. 不许绕过 llm_service 直连 provider —— 出校插桩在 llm_service 里。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services import teaching_review as tr  # noqa: E402

PASS: list = []
FAIL: list = []


def check(name: str, cond: bool, extra: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  {extra}" if extra else ""))


def with_reviewer(fn):
    """打开开关跑一段，跑完恢复，避免污染同批次其他测试。"""
    old = os.environ.get("EDUFORGE_REVIEWER")
    os.environ["EDUFORGE_REVIEWER"] = "1"
    try:
        return fn()
    finally:
        if old is None:
            os.environ.pop("EDUFORGE_REVIEWER", None)
        else:
            os.environ["EDUFORGE_REVIEWER"] = old


def fake_llm(reply: str):
    """把 llm_service.chat 换成固定返回，零额度跑通整条链路。"""
    class Fake:
        def chat(self, message, history=None, knowledge="", provider=None):
            Fake.last_prompt = message
            Fake.last_provider = provider
            return reply

    return Fake()


print("\n=== 1. 默认必须关闭 ===")
os.environ.pop("EDUFORGE_REVIEWER", None)
check("未设开关时 review_enabled=False", tr.review_enabled() is False)
r = tr.review_text("一份教案")
check("关闭时不调模型直接返回", r["enabled"] is False)
check("关闭时给了原因", "未开启" in r["reason"], r["reason"])
check("关闭时 findings 为空", r["findings"] == [])

print("\n=== 2. 空输入与异常都不能炸 ===")


def empty_input():
    return tr.review_text("")


check("空文本不调模型", with_reviewer(empty_input)["enabled"] is False)


def boom():
    class Boom:
        def chat(self, *a, **k):
            raise RuntimeError("模型挂了")

    from app.services import llm_service as ls_mod
    old = ls_mod.llm_service
    ls_mod.llm_service = Boom()
    try:
        return tr.review_text("一份教案")
    finally:
        ls_mod.llm_service = old


res = with_reviewer(boom)
check("模型异常被吞掉不抛出", res["enabled"] is False)
check("异常时给了原因", "失败" in res["reason"], res["reason"])

print("\n=== 3. 结构化输出解析 ===")


def good():
    from app.services import llm_service as ls_mod
    old = ls_mod.llm_service
    fake = fake_llm(
        '```json\n{"summary":"课时偏紧","findings":['
        '{"dimension":"课时可行性","severity":"high","quote":"共安排6个活动","advice":"砍掉2个"},'
        '{"dimension":"科学性","advice":"浮力方向表述有误"}]}\n```'
    )
    ls_mod.llm_service = fake
    try:
        res = tr.review_text("教案正文...浮力产生的原因...", meta={"level": "初中", "topic": "浮力"})
    finally:
        ls_mod.llm_service = old
    return res, fake.last_prompt


res, prompt = with_reviewer(good)
check("围栏 JSON 能解析", res["enabled"] is True)
check("summary 取到", res["summary"] == "课时偏紧", res["summary"])
check("findings 两条", len(res["findings"]) == 2, str(len(res["findings"])))
check("quote 缺失补空", res["findings"][1]["quote"] == "")
check("severity 原样保留", res["findings"][0]["severity"] == "high")
check("五个维度都进了 prompt", all(d in prompt for d in ("课时可行性", "科学性", "教学评一致性")))
check("正文进了 prompt", "浮力产生的原因" in prompt)
check("课程信息进了 prompt", "初中" in prompt and "浮力" in prompt)

print("\n=== 4. 模型乱来时的兜底 ===")


def junk():
    from app.services import llm_service as ls_mod
    old = ls_mod.llm_service
    ls_mod.llm_service = fake_llm("我觉得这份教案还不错，就是有点长。")
    try:
        return tr.review_text("教案正文")
    finally:
        ls_mod.llm_service = old


res = with_reviewer(junk)
check("非 JSON 不丢内容", res["enabled"] is True and res["summary"] != "")
check("非 JSON 标记 raw", res.get("raw") is True)
check("非 JSON 时 findings 为空", res["findings"] == [])


def weird():
    from app.services import llm_service as ls_mod
    old = ls_mod.llm_service
    ls_mod.llm_service = fake_llm(
        '{"summary":"","findings":["砍掉两个活动",{"建议":"换个例子"},{"quote":"x"},null,42]}'
    )
    try:
        return tr.review_text("教案正文")
    finally:
        ls_mod.llm_service = old


res = with_reviewer(weird)
check("字符串条目收下", any(f["advice"] == "砍掉两个活动" for f in res["findings"]))
check("中文键 '建议' 也能取到", any(f["advice"] == "换个例子" for f in res["findings"]))
check("只有 quote 没有 advice 也保留", any(f["quote"] == "x" for f in res["findings"]))
check("null / 数字条目被丢弃", len(res["findings"]) == 3, str(len(res["findings"])))
check("未知 severity 降级为 info", all(
    f["severity"] in ("high", "medium", "low", "info") for f in res["findings"]))


def too_many():
    from app.services import llm_service as ls_mod
    old = ls_mod.llm_service
    ls_mod.llm_service = fake_llm('{"summary":"x","findings":[' + ",".join(
        f'{{"advice":"第{i}条"}}' for i in range(20)
    ) + "]}")
    try:
        return tr.review_text("教案正文")
    finally:
        ls_mod.llm_service = old


check("最多 5 条", len(with_reviewer(too_many)["findings"]) == 5)

print("\n=== 5. 不许绕过出校插桩 ===")
src = (ROOT / "backend/app/services/teaching_review.py").read_text(encoding="utf-8")
check("走的是 llm_service", "from .llm_service import llm_service" in src)
check("没有直连 provider", "get_provider(" not in src)
check("没有自建 http 请求", "requests.post" not in src and "urlopen" not in src)

print(f"\n通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
if FAIL:
    print("失败项：" + "、".join(FAIL))
    sys.exit(1)
