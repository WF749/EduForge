"""Harness 层数据模型（使用标准库 dataclass，零额外依赖）。

关键字段说明：
- degraded: 本次响应是否为"非真实模型生成"（如 demo / 缓存命中 / 兜底模板）。
- source:   响应来源，取值 model | demo | cache | fallback。
任何 degraded=True 的响应，前端都必须明确标注，不得伪装成真实生成。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ChatMessage:
    role: str
    content: str


@dataclass
class LLMResponse:
    content: str
    provider: str
    model: str
    degraded: bool = False
    source: str = "model"  # model | demo | cache | fallback
    finish_reason: Optional[str] = None
    usage: Dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0
    trace_id: Optional[str] = None


@dataclass
class EmbeddingResult:
    vector: List[float]
    model: str
    provider: str
    degraded: bool = False
