"""Harness 离线自测（无需任何 API Key / 网络）。

运行：python backend/tests/test_harness.py
所有用例仅依赖标准库 + 本项目 harness 模块。
"""

import os
import sys

# 让测试能从任意目录运行（app 包位于 backend/ 下）
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.harness import (  # noqa: E402
    CircuitBreaker,
    LLMManager,
    LLMUnavailableError,
    WrappedProvider,
)


class FakeLegacy:
    """一个能正常工作的遗留 Provider 替身。"""

    def chat_completions(self, prompt, history, temperature, api_key, base_url, model):
        return f"[fake-answer] {prompt[-20:]}"

    def get_embeddings(self, text, api_key, base_url, model):
        return [0.1, 0.2, 0.3]

    def test_connection(self, api_key, base_url):
        return {"success": True}


class FlakyLegacy:
    """前 2 次调用必失败，第 3 次成功——用于验证重试。"""

    def __init__(self):
        self.calls = 0

    def chat_completions(self, prompt, history, temperature, api_key, base_url, model):
        self.calls += 1
        if self.calls < 3:
            raise RuntimeError("transient network error")
        return "recovered"

    def get_embeddings(self, text, api_key, base_url, model):
        return [0.0]

    def test_connection(self, api_key, base_url):
        return {"success": True}


class BrokenLegacy:
    """永远失败——用于验证"失败如实抛出"与熔断。"""

    def chat_completions(self, prompt, history, temperature, api_key, base_url, model):
        raise RuntimeError("provider down")

    def get_embeddings(self, text, api_key, base_url, model):
        raise RuntimeError("provider down")

    def test_connection(self, api_key, base_url):
        return {"success": False}


def run():
    passed, failed = 0, 0

    def check(name, cond):
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"  [PASS] {name}")
        else:
            failed += 1
            print(f"  [FAIL] {name}")

    # 1) 成功路径：返回结构化响应，无降级
    wp = WrappedProvider(FakeLegacy(), name="openai", model="gpt-x")
    resp = wp.chat("请生成一元二次方程的导入案例", [], temperature=0.5)
    check("成功调用返回 LLMResponse", resp.content.startswith("[fake-answer]"))
    check("成功调用 latency>0", resp.latency_ms >= 0)
    check("成功调用未标记降级", resp.degraded is False)

    # 2) demo 必须显式标记降级
    demo = WrappedProvider(FakeLegacy(), name="demo")
    dresp = demo.chat("hi", [])
    check("demo 响应标记 degraded", dresp.degraded is True)
    check("demo 响应 source=demo", dresp.source == "demo")

    # 3) 重试生效：Flaky 第 3 次成功
    flaky = WrappedProvider(FlakyLegacy(), name="openai")
    rresp = flaky.chat("retry-me", [])
    check("重试后成功", rresp.content == "recovered")
    check("重试确实发生了多次调用", flaky.legacy.calls >= 3)

    # 4) 失败如实抛出，绝不返回编造内容
    broken = WrappedProvider(BrokenLegacy(), name="openai")
    raised = False
    try:
        broken.chat("boom", [])
    except LLMUnavailableError as e:
        raised = True
        check("失败抛出 LLMUnavailableError", "provider down" in str(e))
    check("失败时未静默返回假内容", raised is True)

    # 5) 熔断器：连续失败达到阈值后拒绝调用
    cb = CircuitBreaker(failure_threshold=3, reset_timeout=0.1)
    breaker_provider = WrappedProvider(BrokenLegacy(), name="openai", breaker=cb)
    for _ in range(3):
        try:
            breaker_provider.chat("x", [])
        except LLMUnavailableError:
            pass
    check("熔断后拒绝调用", cb.allow() is False)
    import time
    time.sleep(0.15)
    check("超时后熔断恢复", cb.allow() is True)

    # 6) Manager 统一入口
    mgr = LLMManager()
    mgr.register("openai", WrappedProvider(FakeLegacy(), name="openai", model="gpt-x"))
    mgr.register("demo", WrappedProvider(FakeLegacy(), name="demo"))
    mresp = mgr.chat("hello via manager", [], provider="openai")
    check("Manager.chat 正常", mresp.content.startswith("[fake-answer]"))
    mdemo = mgr.chat("hi", [], provider="demo")
    check("Manager.demo 标记降级", mdemo.degraded is True)

    # 7) embedding 失败也必须显式暴露（不返回全零向量污染检索）
    eb = WrappedProvider(BrokenLegacy(), name="openai")
    emb_raised = False
    try:
        eb.embed("text")
    except LLMUnavailableError:
        emb_raised = True
    check("embedding 失败如实抛出", emb_raised is True)

    print(f"\n结果：{passed} 通过 / {failed} 失败")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    run()
