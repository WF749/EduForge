"""
数学组件库
包含：坐标系、函数图像、几何图形等
"""
import math
from typing import Dict, Any, List, Callable

from .base_renderer import BaseComponentRenderer
from ..schemas.animation_schema import (
    ComponentType,
    Point,
    Color
)


class CoordinateSystemRenderer(BaseComponentRenderer):
    """坐标系渲染器"""
    
    def __init__(self, position: Point, width: int = 400, height: int = 300,
                 x_min: float = -10, x_max: float = 10,
                 y_min: float = -10, y_max: float = 10,
                 x_label: str = "x", y_label: str = "y",
                 grid_color: Color = None, axis_color: Color = None):
        super().__init__()
        self.position = position
        self.width = width
        self.height = height
        self.x_min = x_min
        self.x_max = x_max
        self.y_min = y_min
        self.y_max = y_max
        self.x_label = x_label
        self.y_label = y_label
        self.grid_color = grid_color or Color(100, 100, 100, 0.3)
        self.axis_color = axis_color or Color(200, 200, 200)
        self.show_grid = True
        self.show_ticks = True
    
    def get_component_type(self) -> ComponentType:
        return ComponentType.COORDINATE_SYSTEM
    
    def render(self, canvas_width: int = 800, canvas_height: int = 600) -> Dict[str, Any]:
        return {
            "id": self.component_id,
            "type": self.get_component_type().value,
            "position": {"x": self.position.x, "y": self.position.y},
            "width": self.width,
            "height": self.height,
            "xRange": [self.x_min, self.x_max],
            "yRange": [self.y_min, self.y_max],
            "labels": {"x": self.x_label, "y": self.y_label},
            "showGrid": self.show_grid,
            "showTicks": self.show_ticks
        }
    
    def generate_js_code(self) -> str:
        return f"""
        // 绘制坐标系
        function drawCoordinateSystem(time) {{
            const centerX = {self.position.x + self.width // 2};
            const centerY = {self.position.y + self.height // 2};
            const width = {self.width};
            const height = {self.height};
            
            // 绘制网格
            {self._generate_grid_js()}
            
            // 绘制坐标轴
            {self._generate_axis_js()}
            
            // 绘制刻度
            {self._generate_ticks_js()}
            
            // 绘制标签
            {self._generate_labels_js()}
        }}
        """
    
    def _generate_grid_js(self) -> str:
        x_range = self.x_max - self.x_min
        y_range = self.y_max - self.y_min
        x_step = max(1, int(x_range / 10))
        y_step = max(1, int(y_range / 10))
        
        return f"""
        ctx.strokeStyle = 'rgba({self.grid_color.r}, {self.grid_color.g}, {self.grid_color.b}, {self.grid_color.a})';
        ctx.lineWidth = 1;
        
        // 垂直网格线
        const xRange = {self.x_max} - {self.x_min};
        const xStep = Math.max(1, Math.floor(xRange / 10));
        for (let x = {self.x_min}; x <= {self.x_max}; x += xStep) {{
            const px = centerX + (x / xRange) * (width / 2) * 2;
            ctx.beginPath();
            ctx.moveTo(px, {self.position.y});
            ctx.lineTo(px, {self.position.y + self.height});
            ctx.stroke();
        }}
        
        // 水平网格线
        const yRange = {self.y_max} - {self.y_min};
        const yStep = Math.max(1, Math.floor(yRange / 10));
        for (let y = {self.y_min}; y <= {self.y_max}; y += yStep) {{
            const py = centerY - (y / yRange) * (height / 2) * 2;
            ctx.beginPath();
            ctx.moveTo({self.position.x}, py);
            ctx.lineTo({self.position.x + self.width}, py);
            ctx.stroke();
        }}
        """
    
    def _generate_axis_js(self) -> str:
        return f"""
        ctx.strokeStyle = 'rgba({self.axis_color.r}, {self.axis_color.g}, {self.axis_color.b}, 1)';
        ctx.lineWidth = 2;
        
        // X轴
        ctx.beginPath();
        ctx.moveTo({self.position.x}, centerY);
        ctx.lineTo({self.position.x + self.width}, centerY);
        ctx.stroke();
        
        // Y轴
        ctx.beginPath();
        ctx.moveTo(centerX, {self.position.y});
        ctx.lineTo(centerX, {self.position.y + self.height});
        ctx.stroke();
        
        // X轴箭头
        ctx.beginPath();
        ctx.moveTo({self.position.x + self.width}, centerY);
        ctx.lineTo({self.position.x + self.width - 10}, centerY - 5);
        ctx.lineTo({self.position.x + self.width - 10}, centerY + 5);
        ctx.closePath();
        ctx.fillStyle = 'rgba({self.axis_color.r}, {self.axis_color.g}, {self.axis_color.b}, 1)';
        ctx.fill();
        
        // Y轴箭头
        ctx.beginPath();
        ctx.moveTo(centerX, {self.position.y});
        ctx.lineTo(centerX - 5, {self.position.y + 10});
        ctx.lineTo(centerX + 5, {self.position.y + 10});
        ctx.closePath();
        ctx.fill();
        """
    
    def _generate_ticks_js(self) -> str:
        return f"""
        ctx.fillStyle = 'rgba({self.axis_color.r}, {self.axis_color.g}, {self.axis_color.b}, 1)';
        ctx.font = '10px Arial';
        ctx.textAlign = 'center';
        
        const xRange = {self.x_max} - {self.x_min};
        const xStep = Math.max(1, Math.floor(xRange / 5));
        for (let x = {self.x_min}; x <= {self.x_max}; x += xStep) {{
            if (x === 0) continue;
            const px = centerX + (x / xRange) * (width / 2) * 2;
            ctx.fillText(x.toString(), px, centerY + 15);
        }}
        
        ctx.textAlign = 'right';
        const yRange = {self.y_max} - {self.y_min};
        const yStep = Math.max(1, Math.floor(yRange / 5));
        for (let y = {self.y_min}; y <= {self.y_max}; y += yStep) {{
            if (y === 0) continue;
            const py = centerY - (y / yRange) * (height / 2) * 2;
            ctx.fillText(y.toString(), centerX - 5, py + 3);
        }}
        """
    
    def _generate_labels_js(self) -> str:
        return f"""
        ctx.fillStyle = 'rgba({self.axis_color.r}, {self.axis_color.g}, {self.axis_color.b}, 1)';
        ctx.font = '12px Arial';
        ctx.textAlign = 'right';
        ctx.fillText('{self.x_label}', {self.position.x + self.width - 5}, centerY - 10);
        ctx.textAlign = 'left';
        ctx.fillText('{self.y_label}', centerX + 10, {self.position.y + 15});
        """


class FunctionGraphRenderer(BaseComponentRenderer):
    """函数图像渲染器"""
    
    def __init__(self, expression: str, 
                 x_min: float = -10, x_max: float = 10,
                 y_min: float = -10, y_max: float = 10,
                 position: Point = None, width: int = 400, height: int = 300,
                 line_color: Color = None, line_width: int = 2):
        super().__init__()
        self.expression = expression
        self.x_min = x_min
        self.x_max = x_max
        self.y_min = y_min
        self.y_max = y_max
        self.position = position or Point(200, 150)
        self.width = width
        self.height = height
        self.line_color = line_color or Color(56, 189, 248)
        self.line_width = line_width
        self.animated = True
    
    def get_component_type(self) -> ComponentType:
        return ComponentType.FUNCTION_GRAPH
    
    def render(self, canvas_width: int = 800, canvas_height: int = 600) -> Dict[str, Any]:
        return {
            "id": self.component_id,
            "type": self.get_component_type().value,
            "expression": self.expression,
            "xRange": [self.x_min, self.x_max],
            "yRange": [self.y_min, self.y_max],
            "position": {"x": self.position.x, "y": self.position.y},
            "width": self.width,
            "height": self.height,
            "lineColor": self.line_color.to_hex(),
            "lineWidth": self.line_width
        }
    
    def generate_js_code(self) -> str:
        center_x = self.position.x + self.width // 2
        center_y = self.position.y + self.height // 2
        x_range = self.x_max - self.x_min
        y_range = self.y_max - self.y_min
        
        js_expression = self._convert_to_js(self.expression)
        
        return f"""
        // 绘制函数图像
        function drawFunctionGraph(time) {{
            const centerX = {center_x};
            const centerY = {center_y};
            const width = {self.width};
            const height = {self.height};
            const xRange = {x_range};
            const yRange = {y_range};
            
            ctx.strokeStyle = 'rgba({self.line_color.r}, {self.line_color.g}, {self.line_color.b}, {self.line_color.a})';
            ctx.lineWidth = {self.line_width};
            ctx.beginPath();
            
            let isFirst = true;
            const progress = Math.min(time * 0.5, 1);
            const maxX = {self.x_min} + xRange * progress;
            
            for (let x = {self.x_min}; x <= maxX; x += 0.05) {{
                try {{
                    const y = {js_expression};
                    if (!isFinite(y)) continue;
                    if (y < {self.y_min} || y > {self.y_max}) {{
                        isFirst = true;
                        continue;
                    }}
                    
                    const px = centerX + (x / xRange) * (width / 2) * 2;
                    const py = centerY - (y / yRange) * (height / 2) * 2;
                    
                    if (isFirst) {{
                        ctx.moveTo(px, py);
                        isFirst = false;
                    }} else {{
                        ctx.lineTo(px, py);
                    }}
                }} catch(e) {{
                    isFirst = true;
                }}
            }}
            ctx.stroke();
        }}
        """
    
    def _convert_to_js(self, expr: str) -> str:
        """将数学表达式转换为JavaScript"""
        conversions = {
            'sin': 'Math.sin',
            'cos': 'Math.cos',
            'tan': 'Math.tan',
            'asin': 'Math.asin',
            'acos': 'Math.acos',
            'atan': 'Math.atan',
            'sqrt': 'Math.sqrt',
            'abs': 'Math.abs',
            'pow': 'Math.pow',
            'exp': 'Math.exp',
            'log': 'Math.log',
            'log10': 'Math.log10',
            'pi': 'Math.PI',
            'PI': 'Math.PI',
            'e': 'Math.E',
            '^': '**',
        }
        
        for old, new in conversions.items():
            expr = expr.replace(old, new)
        
        return expr


class GeometricShapeRenderer(BaseComponentRenderer):
    """几何图形渲染器"""
    
    def __init__(self, shape_type: str, points: List[Point], 
                 fill_color: Color = None, stroke_color: Color = None,
                 line_width: int = 2):
        super().__init__()
        self.shape_type = shape_type
        self.points = points
        self.fill_color = fill_color or Color(56, 189, 248, 0.3)
        self.stroke_color = stroke_color or Color(56, 189, 248)
        self.line_width = line_width
        self.animated = True
    
    def get_component_type(self) -> ComponentType:
        return ComponentType.GEOMETRIC_SHAPE
    
    def render(self, canvas_width: int = 800, canvas_height: int = 600) -> Dict[str, Any]:
        return {
            "id": self.component_id,
            "type": self.get_component_type().value,
            "shapeType": self.shape_type,
            "points": [{"x": p.x, "y": p.y} for p in self.points],
            "fillColor": self.fill_color.to_rgba(),
            "strokeColor": self.stroke_color.to_hex(),
            "lineWidth": self.line_width
        }
    
    def generate_js_code(self) -> str:
        points_js = ", ".join([f"{{x: {p.x}, y: {p.y}}}" for p in self.points])
        
        return f"""
        // 绘制几何图形
        function drawGeometricShape(time) {{
            const points = [{points_js}];
            const progress = Math.min(time * 0.5, 1);
            const numPoints = Math.floor(points.length * progress);
            
            if (numPoints < 2) return;
            
            ctx.fillStyle = 'rgba({self.fill_color.r}, {self.fill_color.g}, {self.fill_color.b}, {self.fill_color.a})';
            ctx.strokeStyle = 'rgba({self.stroke_color.r}, {self.stroke_color.g}, {self.stroke_color.b}, 1)';
            ctx.lineWidth = {self.line_width};
            
            ctx.beginPath();
            ctx.moveTo(points[0].x, points[0].y);
            
            for (let i = 1; i < numPoints; i++) {{
                ctx.lineTo(points[i].x, points[i].y);
            }}
            
            if (progress >= 1) {{
                ctx.closePath();
                ctx.fill();
            }}
            ctx.stroke();
        }}
        """


def create_parabola_demo(position: Point) -> List[str]:
    """创建抛物线演示组件"""
    coord = CoordinateSystemRenderer(position, 500, 400, -5, 5, -2, 10)
    func = FunctionGraphRenderer("x^2", -5, 5, -2, 10, position, 500, 400)
    
    return [
        coord.generate_js_code(),
        func.generate_js_code(),
        """
        function renderScene(time) {
            drawCoordinateSystem(time);
            drawFunctionGraph(time);
        }
        """
    ]


def create_triangle_geometry_demo(position: Point) -> List[str]:
    """创建三角形几何演示"""
    center_x = position.x + 200
    center_y = position.y + 150
    
    points = [
        Point(center_x, center_y - 100),
        Point(center_x - 100, center_y + 80),
        Point(center_x + 100, center_y + 80),
    ]
    
    triangle = GeometricShapeRenderer("triangle", points)
    
    return [
        triangle.generate_js_code(),
        """
        function renderScene(time) {
            drawGeometricShape(time);
        }
        """
    ]
