"""
基础组件渲染器
所有学科组件的基类，提供通用渲染功能
"""
import uuid
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod

from ..schemas.animation_schema import (
    BaseComponent,
    Point,
    Color,
    AnimationEffect,
    AnimationType,
    EasingType,
    ComponentType
)


class BaseComponentRenderer(ABC):
    """组件渲染器基类"""
    
    def __init__(self):
        self.component_id = f"comp_{uuid.uuid4().hex[:8]}"
        self.style = {}
        self.animations = []
    
    @abstractmethod
    def render(self, canvas_width: int = 800, canvas_height: int = 600) -> Dict[str, Any]:
        """渲染组件为可执行的配置"""
        pass
    
    def to_component(self) -> BaseComponent:
        """转换为基础组件对象"""
        return BaseComponent(
            id=self.component_id,
            type=self.get_component_type(),
            style=self.style
        )
    
    @abstractmethod
    def get_component_type(self) -> ComponentType:
        """获取组件类型"""
        pass
    
    def generate_js_code(self) -> str:
        """生成JavaScript渲染代码"""
        return ""
    
    def _generate_animation_code(self, effect: AnimationEffect, var_name: str) -> str:
        """生成动画代码"""
        easing_map = {
            EasingType.LINEAR: "linear",
            EasingType.EASE_IN: "easeIn",
            EasingType.EASE_OUT: "easeOut",
            EasingType.EASE_IN_OUT: "easeInOut",
            EasingType.BOUNCE: "bounce",
            EasingType.ELASTIC: "elastic",
        }
        
        easing = easing_map.get(effect.easing, "easeInOut")
        
        if effect.type == AnimationType.FADE:
            return f"animateFade({var_name}, {effect.duration}, '{easing}');"
        elif effect.type == AnimationType.SLIDE:
            return f"animateSlide({var_name}, {effect.duration}, '{easing}');"
        elif effect.type == AnimationType.SCALE:
            return f"animateScale({var_name}, {effect.duration}, '{easing}');"
        elif effect.type == AnimationType.ROTATE:
            return f"animateRotate({var_name}, {effect.duration}, '{easing}');"
        elif effect.type == AnimationType.PATH:
            return f"animatePath({var_name}, {effect.duration}, '{easing}');"
        
        return ""


class ShapeRenderer(BaseComponentRenderer):
    """基础形状渲染器"""
    
    def __init__(self, position: Point, color: Color):
        super().__init__()
        self.position = position
        self.color = color
        self.line_width = 2
        self.fill = True
        self.stroke_color = None
    
    def render(self, canvas_width: int = 800, canvas_height: int = 600) -> Dict[str, Any]:
        return {
            "id": self.component_id,
            "type": self.get_component_type().value,
            "position": {"x": self.position.x, "y": self.position.y},
            "color": {
                "r": self.color.r,
                "g": self.color.g,
                "b": self.color.b,
                "a": self.color.a
            },
            "lineWidth": self.line_width,
            "fill": self.fill,
            "strokeColor": self.stroke_color.to_rgba() if self.stroke_color else None
        }


class CircleRenderer(ShapeRenderer):
    """圆形渲染器"""
    
    def __init__(self, position: Point, radius: int, color: Color):
        super().__init__(position, color)
        self.radius = radius
    
    def get_component_type(self) -> ComponentType:
        return ComponentType.CIRCLE
    
    def render(self, canvas_width: int = 800, canvas_height: int = 600) -> Dict[str, Any]:
        config = super().render(canvas_width, canvas_height)
        config["radius"] = self.radius
        return config
    
    def generate_js_code(self) -> str:
        return f"""
        // 绘制圆形
        ctx.beginPath();
        ctx.arc({self.position.x}, {self.position.y}, {self.radius}, 0, Math.PI * 2);
        {self._generate_style_code()}
        ctx.fill();
        ctx.stroke();
        """
    
    def _generate_style_code(self) -> str:
        return f"""
        ctx.fillStyle = 'rgba({self.color.r}, {self.color.g}, {self.color.b}, {self.color.a})';
        ctx.strokeStyle = '{self.stroke_color.to_hex() if self.stroke_color else "transparent"}';
        ctx.lineWidth = {self.line_width};
        """


class RectangleRenderer(ShapeRenderer):
    """矩形渲染器"""
    
    def __init__(self, position: Point, width: int, height: int, color: Color):
        super().__init__(position, color)
        self.width = width
        self.height = height
    
    def get_component_type(self) -> ComponentType:
        return ComponentType.RECTANGLE
    
    def render(self, canvas_width: int = 800, canvas_height: int = 600) -> Dict[str, Any]:
        config = super().render(canvas_width, canvas_height)
        config["width"] = self.width
        config["height"] = self.height
        return config
    
    def generate_js_code(self) -> str:
        return f"""
        // 绘制矩形
        ctx.fillStyle = 'rgba({self.color.r}, {self.color.g}, {self.color.b}, {self.color.a})';
        ctx.fillRect({self.position.x}, {self.position.y}, {self.width}, {self.height});
        ctx.strokeStyle = '{self.stroke_color.to_hex() if self.stroke_color else "transparent"}';
        ctx.lineWidth = {self.line_width};
        ctx.strokeRect({self.position.x}, {self.position.y}, {self.width}, {self.height});
        """


class TextRenderer(ShapeRenderer):
    """文本渲染器"""
    
    def __init__(self, position: Point, text: str, color: Color, 
                 font_size: int = 16, font_family: str = "Microsoft YaHei"):
        super().__init__(position, color)
        self.text = text
        self.font_size = font_size
        self.font_family = font_family
        self.align = "center"
        self.baseline = "middle"
    
    def get_component_type(self) -> ComponentType:
        return ComponentType.TEXT
    
    def render(self, canvas_width: int = 800, canvas_height: int = 600) -> Dict[str, Any]:
        config = super().render(canvas_width, canvas_height)
        config.update({
            "text": self.text,
            "fontSize": self.font_size,
            "fontFamily": self.font_family,
            "textAlign": self.align,
            "textBaseline": self.baseline
        })
        return config
    
    def generate_js_code(self) -> str:
        return f"""
        // 绘制文本
        ctx.fillStyle = 'rgba({self.color.r}, {self.color.g}, {self.color.b}, {self.color.a})';
        ctx.font = '{self.font_size}px {self.font_family}';
        ctx.textAlign = '{self.align}';
        ctx.textBaseline = '{self.baseline}';
        ctx.fillText('{self.text}', {self.position.x}, {self.position.y});
        """


class ArrowRenderer(ShapeRenderer):
    """箭头渲染器"""
    
    def __init__(self, start: Point, end: Point, color: Color, 
                 head_width: int = 15, head_length: int = 20):
        super().__init__(start, color)
        self.start = start
        self.end = end
        self.head_width = head_width
        self.head_length = head_length
    
    def get_component_type(self) -> ComponentType:
        return ComponentType.ARROW
    
    def render(self, canvas_width: int = 800, canvas_height: int = 600) -> Dict[str, Any]:
        config = super().render(canvas_width, canvas_height)
        config.update({
            "start": {"x": self.start.x, "y": self.start.y},
            "end": {"x": self.end.x, "y": self.end.y},
            "headWidth": self.head_width,
            "headLength": self.head_length
        })
        return config
    
    def generate_js_code(self) -> str:
        return f"""
        // 绘制箭头
        drawArrow(ctx, {self.start.x}, {self.start.y}, {self.end.x}, {self.end.y}, 
                  'rgba({self.color.r}, {self.color.g}, {self.color.b}, {self.color.a})', {self.line_width});
        """


class ComponentLibrary:
    """组件库 - 管理所有可用组件"""
    
    def __init__(self):
        self.renderers = {}
        self._register_renderers()
    
    def _register_renderers(self):
        """注册渲染器"""
        self.renderers[ComponentType.CIRCLE] = CircleRenderer
        self.renderers[ComponentType.RECTANGLE] = RectangleRenderer
        self.renderers[ComponentType.TEXT] = TextRenderer
        self.renderers[ComponentType.ARROW] = ArrowRenderer
    
    def create_component(self, component_type: ComponentType, **kwargs) -> Optional[BaseComponentRenderer]:
        """创建组件"""
        renderer_class = self.renderers.get(component_type)
        if renderer_class:
            return renderer_class(**kwargs)
        return None
    
    def get_supported_types(self) -> List[ComponentType]:
        """获取支持的组件类型"""
        return list(self.renderers.keys())


# 全局组件库实例
component_library = ComponentLibrary()


# 辅助函数
def generate_canvas_wrapper(components: List[str], title: str = "教学动画", 
                            width: int = 800, height: int = 600) -> str:
    """生成Canvas包装HTML代码"""
    components_js = "\n".join(components)
    
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Microsoft YaHei', sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 20px;
            color: #e2e8f0;
        }}
        .container {{
            background: rgba(30, 41, 59, 0.8);
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(148, 163, 184, 0.1);
        }}
        h1 {{
            text-align: center;
            margin-bottom: 20px;
            font-size: 24px;
            font-weight: 600;
            background: linear-gradient(90deg, #38bdf8, #a78bfa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        #animationCanvas {{
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
            display: block;
        }}
        .controls {{
            margin-top: 20px;
            display: flex;
            gap: 12px;
            justify-content: center;
            flex-wrap: wrap;
        }}
        button {{
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.3s ease;
            font-family: inherit;
        }}
        .btn-primary {{
            background: linear-gradient(135deg, #38bdf8, #0ea5e9);
            color: white;
        }}
        .btn-primary:hover {{
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(56, 189, 248, 0.4);
        }}
        .btn-secondary {{
            background: rgba(148, 163, 184, 0.2);
            color: #e2e8f0;
            border: 1px solid rgba(148, 163, 184, 0.3);
        }}
        .btn-secondary:hover {{
            background: rgba(148, 163, 184, 0.3);
        }}
        .info-panel {{
            margin-top: 20px;
            padding: 16px;
            background: rgba(15, 23, 42, 0.6);
            border-radius: 8px;
            border-left: 4px solid #38bdf8;
            max-width: 600px;
        }}
        .info-title {{
            font-weight: 600;
            margin-bottom: 8px;
            color: #38bdf8;
        }}
        .info-content {{
            font-size: 14px;
            line-height: 1.6;
            color: #94a3b8;
        }}
        .progress-bar {{
            width: 100%;
            height: 6px;
            background: rgba(148, 163, 184, 0.2);
            border-radius: 3px;
            margin-top: 16px;
            overflow: hidden;
        }}
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, #38bdf8, #a78bfa);
            border-radius: 3px;
            transition: width 0.3s ease;
            width: 0%;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{title}</h1>
        <canvas id="animationCanvas" width="{width}" height="{height}"></canvas>
        <div class="progress-bar">
            <div class="progress-fill" id="progressFill"></div>
        </div>
        <div class="controls">
            <button class="btn-primary" id="playBtn">播放/暂停</button>
            <button class="btn-secondary" id="resetBtn">重置</button>
            <button class="btn-secondary" id="slowBtn">慢速</button>
        </div>
        <div class="info-panel">
            <div class="info-title">知识点</div>
            <div class="info-content" id="infoContent">点击动画中的元素查看详细说明</div>
        </div>
    </div>

    <script>
        const canvas = document.getElementById('animationCanvas');
        const ctx = canvas.getContext('2d');
        const progressFill = document.getElementById('progressFill');
        const infoContent = document.getElementById('infoContent');
        
        let isPlaying = true;
        let animationTime = 0;
        let speedMultiplier = 1;
        let lastTimestamp = 0;
        
        // 辅助函数：绘制箭头
        function drawArrow(ctx, fromX, fromY, toX, toY, color, lineWidth = 2) {{
            const headLength = 15;
            const angle = Math.atan2(toY - fromY, toX - fromX);
            
            ctx.beginPath();
            ctx.moveTo(fromX, fromY);
            ctx.lineTo(toX, toY);
            ctx.strokeStyle = color;
            ctx.lineWidth = lineWidth;
            ctx.stroke();
            
            ctx.beginPath();
            ctx.moveTo(toX, toY);
            ctx.lineTo(toX - headLength * Math.cos(angle - Math.PI / 6), 
                       toY - headLength * Math.sin(angle - Math.PI / 6));
            ctx.lineTo(toX - headLength * Math.cos(angle + Math.PI / 6), 
                       toY - headLength * Math.sin(angle + Math.PI / 6));
            ctx.closePath();
            ctx.fillStyle = color;
            ctx.fill();
        }}
        
        // 辅助函数：缓动函数
        function easeInOut(t) {{
            return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
        }}
        
        function easeOut(t) {{
            return 1 - Math.pow(1 - t, 3);
        }}
        
        function easeIn(t) {{
            return t * t * t;
        }}
        
        function bounce(t) {{
            const n1 = 7.5625;
            const d1 = 2.75;
            if (t < 1 / d1) {{
                return n1 * t * t;
            }} else if (t < 2 / d1) {{
                return n1 * (t -= 1.5 / d1) * t + 0.75;
            }} else if (t < 2.5 / d1) {{
                return n1 * (t -= 2.25 / d1) * t + 0.9375;
            }} else {{
                return n1 * (t -= 2.625 / d1) * t + 0.984375;
            }}
        }}
        
        // 组件渲染
        {components_js}
        
        // 主渲染循环
        function render(timestamp) {{
            if (!lastTimestamp) lastTimestamp = timestamp;
            const deltaTime = (timestamp - lastTimestamp) / 1000;
            lastTimestamp = timestamp;
            
            if (isPlaying) {{
                animationTime += deltaTime * speedMultiplier;
            }}
            
            // 清空画布
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            // 绘制背景渐变
            const gradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
            gradient.addColorStop(0, '#0f172a');
            gradient.addColorStop(1, '#1e293b');
            ctx.fillStyle = gradient;
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            
            // 绘制网格背景
            ctx.strokeStyle = 'rgba(148, 163, 184, 0.05)';
            ctx.lineWidth = 1;
            for (let i = 0; i < canvas.width; i += 40) {{
                ctx.beginPath();
                ctx.moveTo(i, 0);
                ctx.lineTo(i, canvas.height);
                ctx.stroke();
            }}
            for (let i = 0; i < canvas.height; i += 40) {{
                ctx.beginPath();
                ctx.moveTo(0, i);
                ctx.lineTo(canvas.width, i);
                ctx.stroke();
            }}
            
            // 调用场景渲染
            renderScene(animationTime);
            
            // 更新进度条
            const progress = Math.min((animationTime % 30) / 30 * 100, 100);
            progressFill.style.width = progress + '%';
            
            requestAnimationFrame(render);
        }}
        
        // 控制按钮
        document.getElementById('playBtn').addEventListener('click', function() {{
            isPlaying = !isPlaying;
            this.textContent = isPlaying ? '暂停' : '播放';
        }});
        
        document.getElementById('resetBtn').addEventListener('click', function() {{
            animationTime = 0;
            isPlaying = true;
            document.getElementById('playBtn').textContent = '暂停';
        }});
        
        document.getElementById('slowBtn').addEventListener('click', function() {{
            speedMultiplier = speedMultiplier === 1 ? 0.5 : 1;
            this.textContent = speedMultiplier === 1 ? '慢速' : '正常';
        }});
        
        // 开始动画
        requestAnimationFrame(render);
    </script>
</body>
</html>
"""
