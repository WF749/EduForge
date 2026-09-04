"""数据合规：识别 → 定级 → 路由决策 → 脱敏。

为什么必须有这个模块
--------------------
本项目的核心定位是"数据不出校"。但在此之前，这条主张是**无法自证**的：

  - RAG 检索与重排序已本地化（见 docs/RAG.md）
  - 但教案 / PPT / 游戏 / 动画的生成仍走云端 LLM
  - 代码里没有任何敏感数据识别、分级或拦截

也就是说，教师若把月考错题或学生名单写进"课题/要求"，
内容会原样发往云端厂商 —— 我们宣称的护城河，在最主要的功能上并不成立。

本模块把这件事变成可执行的判定：

  1. `classifier`  识别输入中的敏感信息并定级（对齐 JY/T 0661-2025 的 L1–L5）
  2. `policy`      判断本次调用是否出校，并按策略决定放行/告警/阻断/脱敏
  3. `redact`      确需上云时，保留教学语义、抹掉身份标识

设计底线（与项目其余部分一致）
------------------------------
- **绝不静默处理**：定级结果必须可查（响应头 / 追踪 / 扫描接口），
  教师与管理员能看见"这次生成的数据去了哪"。
- **策略默认不改变现有行为**：`EDUFORGE_SAFETY_MODE` 默认 `warn`，
  只记录与告警。要真正阻断需显式设为 `enforce`。
  这是刻意的 —— 默认阻断会让任何粘贴了手机号的用户突然用不了，
  属于把策略选择偷偷做成产品行为。
- **判定失败要显式报错**，不能因为"检测出错"就放行。
"""

from .classifier import (
    LEVELS,
    Classification,
    Finding,
    classify,
    level_rank,
)
from .policy import (
    RouteDecision,
    SAFETY_MODES,
    decide,
    get_safety_mode,
    is_private_endpoint,
)
from .redact import redact

__all__ = [
    "LEVELS", "Classification", "Finding", "classify", "level_rank",
    "RouteDecision", "SAFETY_MODES", "decide", "get_safety_mode",
    "is_private_endpoint", "redact",
]
