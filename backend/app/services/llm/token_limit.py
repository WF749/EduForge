"""LLM 输出上限（max_tokens）的统一解析。

为什么需要它 —— 一次真实故障（2026-09-06 修复）：
    dashscope provider 原先硬编码 `max_tokens=4096`，而教案这类产物需要
    一次性生成十几个模块，输出远超该值 → 被**硬截断**（finish_reason='length'）
    → 返回不完整的 JSON → 下游解析后得到**全空内容**，
    表现为「接口返回成功、耗时正常，但内容一片空白」，且日志无任何报错，
    极难排查。

    排查时其余 provider 存在完全相同的隐患：
      zhipu / deepseek / openai = 4096，local / anthropic / moonshot = 2048。
    故统一收敛到本模块，避免各自为政、再次踩坑。

优先级：环境变量 EDUFORGE_LLM_MAX_TOKENS > 调用方传入的 default。
"""
from __future__ import annotations

import os

# 生成型任务（教案 / PPT / 动画 / 游戏）的输出上限
DEFAULT_MAX_TOKENS = 8192

_ENV = "EDUFORGE_LLM_MAX_TOKENS"


def resolve_max_tokens(default: int = DEFAULT_MAX_TOKENS) -> int:
    """解析输出上限。

    :param default: 未设置环境变量时使用的默认值
    :return: 正整数；环境变量为非法值时静默回退到 default
    """
    raw = os.getenv(_ENV)
    if raw:
        try:
            value = int(raw)
            if value > 0:
                return value
        except ValueError:
            pass
    return default
