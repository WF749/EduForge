"""诊断：教案生成「阶段3 精细化内容」是否因 max_tokens 截断而产出空模块。

做法：hook dashscope.Generation.call，记录每次调用的 finish_reason 与返回长度。
finish_reason == 'length' 即为被 max_tokens 截断的铁证。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import dashscope  # noqa: E402

CAPTURED: list = []
_orig_call = dashscope.Generation.call


def spy(*args, **kwargs):
    resp = _orig_call(*args, **kwargs)
    try:
        out = resp.output
        CAPTURED.append({
            "finish_reason": getattr(out, "finish_reason", None),
            "text_len": len(getattr(out, "text", "") or ""),
            "max_tokens": kwargs.get("max_tokens"),
            "model": kwargs.get("model"),
        })
        print(f"[DIAG] finish_reason={getattr(out,'finish_reason',None)} "
              f"text_len={len(getattr(out,'text','') or '')} "
              f"max_tokens={kwargs.get('max_tokens')} model={kwargs.get('model')}")
    except Exception as e:  # noqa: BLE001
        print(f"[DIAG] 读取响应失败: {e}")
    return resp


dashscope.Generation.call = spy

from app.services.llm_lesson_plan_all_stages import LessonPlanGenerator  # noqa: E402


def main() -> int:
    gen = LessonPlanGenerator()

    requirements = {
        "basic_info": {
            "level": "初中",
            "subject": "物理",
            "grade": "八年级",
            "topic": "浮力",
            "duration": 45,
            "requirements": "",
        }
    }
    # 与真实流程中 generate_outline 的返回结构保持一致
    outline = {
        "modules": [
            "教案基本信息", "教学目标", "教学重难点", "教学准备",
            "教学过程设计", "板书设计/课件框架", "作业布置与课后拓展",
            "教学反思与应急预案", "核心素养与中考对标", "思维能力培养设计",
            "分层教学与学困生帮扶", "探究式学习环节",
        ],
        "sections": ["导入", "新知讲解", "小组讨论", "练习巩固", "总结提升"],
    }

    print("== 阶段3：generate_detailed_content ==")
    lp = gen.generate_detailed_content(outline, requirements)

    print("\n== 解析结果 ==")
    for k, v in lp.items():
        if isinstance(v, dict):
            n = len(v)
        elif isinstance(v, list):
            n = len(v)
        else:
            n = len(str(v)) if v is not None else 0
        print(f"  {k}: {type(v).__name__} 有效长度={n}")

    print("\n== LLM 调用记录 ==")
    for c in CAPTURED:
        print(f"  {c}")
        if c["finish_reason"] == "length":
            print("  ⚠️ 输出被 max_tokens 截断（finish_reason=length）")

    empty = sum(
        1 for v in lp.values()
        if (isinstance(v, (dict, list)) and len(v) == 0)
    )
    print(f"\n空模块数: {empty} / {len(lp)}")
    if any(c["finish_reason"] == "length" for c in CAPTURED):
        print("结论：根因确认为 max_tokens 截断")
        return 2
    if empty:
        print("结论：内容为空，但未检测到截断 —— 需查解析逻辑")
        return 1
    print("结论：本次生成正常")
    return 0


if __name__ == "__main__":
    sys.exit(main())
