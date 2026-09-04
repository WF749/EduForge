"""教案生成健壮性冒烟测试（**不调模型**，秒级完成）。

存在的理由：2026-09-05 线上出现过「教案生成返回成功，但 12 个模块内容全空」的故障。
排查下来是两个彼此独立的缺陷叠加：
  1. dashscope 的 max_tokens 只有 4096，12 个模块的完整教案输出会被硬截断
     （finish_reason='length'），返回不完整 JSON → 下游解析出全空模块；
  2. _ensure_content_completeness 对「教学目标/教学过程设计」遇到非 list 形态
     （模型常输出 dict）时**直接置空**，把模型已经生成好的内容丢掉。

这里把两条都钉死，防止以后改回去。

诊断脚本（会真实调模型、较慢）见 scripts/diag_lesson_plan_stage3.py。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.llm.dashscope import _resolve_max_tokens  # noqa: E402
from app.services.llm_lesson_plan_all_stages import LessonPlanGenerator  # noqa: E402

PASS: list = []
FAIL: list = []


def check(name: str, cond: bool, extra: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  {extra}" if extra else ""))


def test_max_tokens_floor() -> None:
    """输出上限必须足够大，否则长教案会被截断成空。"""
    print("\n== 1. LLM 输出上限（防截断）==")
    mt = _resolve_max_tokens()
    check("max_tokens >= 8192", mt >= 8192, f"(实际 {mt})")
    # 4096 是历史上导致截断的值，明确禁止回退
    check("max_tokens 不等于历史缺陷值 4096", mt != 4096, f"(实际 {mt})")

    # 可通过环境变量覆盖
    os.environ["EDUFORGE_LLM_MAX_TOKENS"] = "16384"
    check("环境变量可覆盖", _resolve_max_tokens() == 16384)
    os.environ["EDUFORGE_LLM_MAX_TOKENS"] = "not-a-number"
    check("非法环境变量回退到默认值", _resolve_max_tokens() >= 8192)
    del os.environ["EDUFORGE_LLM_MAX_TOKENS"]


def test_completeness_keeps_content() -> None:
    """补全逻辑必须保住模型已生成的内容，不能一丢了之。"""
    print("\n== 2. 内容完整性补全（不丢内容）==")
    gen = LessonPlanGenerator()

    # 模型把教学目标输出成 dict 是最常见的情况（按素养维度分组）
    lp = gen._ensure_content_completeness(
        {"教学目标": {"文化自信": ["能背诵古诗"], "语言运用": ["能概括段意"]},
         "教学过程设计": [{"环节": "导入"}]},
        "初中", "物理")
    goals = lp.get("教学目标")
    check("教学目标为 dict 时内容被保留（不置空）",
          isinstance(goals, dict) and len(goals) == 2, f"(实际 {goals})")

    # 字符串形态应转成单元素列表，而不是丢掉
    lp2 = gen._ensure_content_completeness(
        {"教学目标": "掌握浮力概念", "教学过程设计": [{"环节": "导入"}]},
        "初中", "物理")
    check("教学目标为 str 时转成列表且保留",
          lp2.get("教学目标") == ["掌握浮力概念"], f"(实际 {lp2.get('教学目标')})")

    # 真空值才允许降级为空列表
    lp3 = gen._ensure_content_completeness(
        {"教学目标": {}, "教学过程设计": [{"环节": "导入"}]},
        "初中", "物理")
    check("教学目标为空时才降级为空列表", lp3.get("教学目标") == [])

    # 教学过程设计下游按 list 渲染表格，dict 需适配成 list 且保住内容
    lp4 = gen._ensure_content_completeness(
        {"教学过程设计": {"导入": "5分钟"}, "教学目标": ["目标A"]},
        "初中", "物理")
    proc = lp4.get("教学过程设计")
    check("教学过程设计为 dict 时适配成 list",
          isinstance(proc, list) and len(proc) == 1, f"(实际 {proc})")
    check("教学过程设计适配后未丢内容",
          isinstance(proc, list) and proc and proc[0].get("导入") == "5分钟")


def test_required_modules() -> None:
    """缺失的必填模块要被补齐，且类型符合下游预期。"""
    print("\n== 3. 必填模块补齐 ==")
    gen = LessonPlanGenerator()
    lp = gen._ensure_content_completeness({}, "初中", "物理")
    for m in ("教案基本信息", "教学重难点", "教学准备"):
        check(f"补齐模块「{m}」", m in lp and isinstance(lp[m], dict))
    check("补齐「教学目标」为 list", isinstance(lp.get("教学目标"), list))
    check("补齐「教学过程设计」为 list", isinstance(lp.get("教学过程设计"), list))


def test_all_providers_unified_limit() -> None:
    """所有真实 provider 的生成入口都必须走统一上限。

    用源码静态检查兜底：防止以后新增 provider 时又硬编码一个小值，
    把「输出被截断 → 内容全空」的故障再带回來一次。
    """
    print("\n== 4. 各 provider 统一输出上限（静态检查）==")
    llm_dir = ROOT / "backend" / "app" / "services" / "llm"
    # 排除：base（抽象基类）、service（服务层）、demo（返回模板，不调模型）、
    #       gemini（未显式设置 max_tokens，由 API 默认值决定）
    skip = {"base.py", "service.py", "demo.py", "gemini.py",
            "__init__.py", "token_limit.py"}

    checked = 0
    for f in sorted(llm_dir.glob("*.py")):
        if f.name in skip:
            continue
        src = f.read_text(encoding="utf-8")
        if "def chat_completions(" not in src:
            continue
        # 只取 chat_completions 方法体（截到下一个方法定义为止）
        body = src.split("def chat_completions(", 1)[1]
        for marker in ("def stream_chat_completions(", "\n    def "):
            if marker in body:
                body = body.split(marker, 1)[0]
        checked += 1
        check(f"{f.name} 的 chat_completions 走统一上限",
              "resolve_max_tokens" in body)
        check(f"{f.name} 未残留硬编码的历史缺陷值",
              not any(v in body for v in
                      ('"max_tokens": 4096', '"max_tokens": 2048', "max_tokens=4096")))

    check("覆盖全部 7 个真实 provider", checked == 7, f"(实际 {checked})")


def main() -> int:
    print("教案生成健壮性冒烟测试（不调模型）")
    test_max_tokens_floor()
    test_completeness_keeps_content()
    test_required_modules()
    test_all_providers_unified_limit()

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
