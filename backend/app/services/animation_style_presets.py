"""教学动画视觉风格预设（与前端选项一一对应，影响配色与版式）"""

from typing import Dict, Any

# id 与前端 AnimationView / get_animation_styles 一致
ANIMATION_STYLE_PRESETS: Dict[str, Dict[str, Any]] = {
    "2D动画": {
        "label": "2D扁平科技",
        "bg": "#0a0e27",
        "panel": "#12163a",
        "accent1": "#00d4ff",
        "accent2": "#7c3aed",
        "text": "#e8eef7",
        "muted": "#8899bb",
        "llm_hint": "扁平矢量感、高对比、深蓝背景、青紫渐变点缀",
    },
    "3D动画": {
        "label": "3D科技空间",
        "bg": "#1a1a2e",
        "panel": "#16213e",
        "accent1": "#e94560",
        "accent2": "#533483",
        "text": "#eaeaea",
        "muted": "#a0a0b8",
        "llm_hint": "立体感块面、光影分区、红紫对比、略深背景",
    },
    "手绘风": {
        "label": "手绘插画",
        "bg": "#faf3e0",
        "panel": "#fff8e7",
        "accent1": "#bc6c25",
        "accent2": "#606c38",
        "text": "#3c2f2f",
        "muted": "#6b5b4f",
        "llm_hint": "纸张质感、柔和描边、暖色、手绘线条与色块",
    },
    "卡通": {
        "label": "儿童卡通",
        "bg": "#e8f4fc",
        "panel": "#ffffff",
        "accent1": "#ff6b9d",
        "accent2": "#5dade2",
        "text": "#2c3e50",
        "muted": "#7f8c8d",
        "llm_hint": "圆润大色块、高饱和、友好卡通造型",
    },
    "白板": {
        "label": "白板讲解",
        "bg": "#f2f2f0",
        "panel": "#ffffff",
        "accent1": "#1a1a1a",
        "accent2": "#0066cc",
        "text": "#222222",
        "muted": "#555555",
        "llm_hint": "白底为主、深色马克笔线条、少量蓝色强调，像课堂白板",
    },
}


def get_preset(style_id: str) -> Dict[str, Any]:
    return ANIMATION_STYLE_PRESETS.get(style_id, ANIMATION_STYLE_PRESETS["2D动画"])


def style_list_for_api() -> list:
    """供 GET /animation/styles 使用"""
    return [
        {"id": k, "name": v["label"], "description": f"配色与版式：{v['llm_hint']}", "visual": True}
        for k, v in ANIMATION_STYLE_PRESETS.items()
    ]
