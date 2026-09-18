"""LLM 服务「不把失败伪装成成功」冒烟测试（**不调模型**，秒级完成）。

存在的理由：docs/CONSTRAINTS.md D2 早就写了「模型调用失败必须显式标记，绝不静默兜底」，
但 `services/llm/service.py` 的流式链路长期存在相反的行为 ——
真实模型重试 3 次失败后直接切 DemoProvider 输出模板内容，且不标记降级。

后果是**静默的**：教师看到一段通顺的内容，以为模型真的给了建议，
拿去上课才发现是模板。这类问题不会报错、不会被日志捕获，只能靠测试钉死。

这里同时钉住一个容易反复的细节：**降级提示必须先于模板内容产出**。
顺序反了的话，用户先读到模板、再读到"这是模板"，等于没说。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.llm.service import (  # noqa: E402
    _demo_fallback_allowed, _failure_notice, _demo_notice, LLMService,
)

PASS: list = []
FAIL: list = []


def check(name: str, cond: bool, extra: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  {extra}" if extra else ""))


class _ExplodingProvider:
    """真实模型不可用：每次调用都抛错。"""

    def stream_chat_completions(self, **kwargs):
        raise RuntimeError("上游 502")


class _DemoProvider:
    """演示模板：产出固定的模板内容。"""

    def stream_chat_completions(self, **kwargs):
        yield "【模板】这是一段演示内容。"


def _make_service(provider_name: str = "dashscope"):
    """构造一个不碰数据库的 LLMService。

    直接走 __new__ 跳过 _init()：_init 会建 sqlite 连接与表，
    冒烟测试不应该动用户的 llm_config.db。
    """
    svc = LLMService.__new__(LLMService)
    providers = {"dashscope": _ExplodingProvider(), "demo": _DemoProvider()}
    svc.providers = providers
    svc.get_provider = lambda name: providers.get(name) or _ExplodingProvider()
    svc._resolve_runtime_config = lambda *a, **k: {
        "provider": provider_name, "api_key": "k", "base_url": "http://127.0.0.1:1",
        "model": "m", "temperature": 0.7,
    }
    return svc


def _collect(svc) -> str:
    return "".join(svc.stream_chat_completions(prompt="讲一次函数", history=[]))


# ---------------------------------------------------------------------------
def test_switch_default_off() -> None:
    print("\n== 1. 降级开关默认关闭 ==")
    os.environ.pop("EDUFORGE_LLM_FALLBACK_TO_DEMO", None)
    check("默认不降级", _demo_fallback_allowed() is False)

    os.environ["EDUFORGE_LLM_FALLBACK_TO_DEMO"] = "true"
    check("显式开启可降级", _demo_fallback_allowed() is True)

    os.environ["EDUFORGE_LLM_FALLBACK_TO_DEMO"] = "0"
    check("显式写 0 仍不降级", _demo_fallback_allowed() is False)
    os.environ.pop("EDUFORGE_LLM_FALLBACK_TO_DEMO", None)


def test_no_silent_fallback() -> None:
    print("\n== 2. 未开启降级时，绝不能产出模板内容 ==")
    os.environ.pop("EDUFORGE_LLM_FALLBACK_TO_DEMO", None)
    out = _collect(_make_service("dashscope"))

    check("输出里没有模板正文", "【模板】" not in out)
    check("明确告知生成失败", "[生成失败]" in out)
    check("带上可操作的失败原因", "上游 502" in out)


def test_fallback_is_announced() -> None:
    print("\n== 3. 开启降级时，必须先声明再给内容 ==")
    os.environ["EDUFORGE_LLM_FALLBACK_TO_DEMO"] = "true"
    try:
        out = _collect(_make_service("dashscope"))
    finally:
        os.environ.pop("EDUFORGE_LLM_FALLBACK_TO_DEMO", None)

    check("确实降级出了模板内容", "【模板】" in out)
    check("声明了这是演示兜底", "[演示模式兜底]" in out)
    check("提示出现在模板内容之前",
          out.index("[演示模式兜底]") < out.index("【模板】"))


def test_explicit_demo_is_not_a_fallback() -> None:
    """用户主动选了演示模式，它就该失败 —— 不能"兜底"成它自己。"""
    print("\n== 4. 显式选择演示模式时不算兜底 ==")
    os.environ["EDUFORGE_LLM_FALLBACK_TO_DEMO"] = "true"
    try:
        svc = _make_service("demo")
        svc.providers["demo"] = _ExplodingProvider()
        out = _collect(svc)
    finally:
        os.environ.pop("EDUFORGE_LLM_FALLBACK_TO_DEMO", None)

    check("不冒充演示兜底", "[演示模式兜底]" not in out)
    check("如实报失败", "[生成失败]" in out)


def test_notice_text() -> None:
    print("\n== 5. 提示文案本身 ==")
    fail_msg = _failure_notice("boom")
    demo_msg = _demo_notice("boom")
    check("失败提示说明没有产出内容", "没有产出任何内容" in fail_msg)
    check("降级提示说明不是真实模型输出", "并非真实模型输出" in demo_msg)
    check("两条提示都带原因", "boom" in fail_msg and "boom" in demo_msg)


def main() -> int:
    print("LLM 服务「不把失败伪装成成功」冒烟测试（不调模型）")
    test_switch_default_off()
    test_no_silent_fallback()
    test_fallback_is_announced()
    test_explicit_demo_is_not_a_fallback()
    test_notice_text()

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
