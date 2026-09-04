"""
生物组件库
包含：细胞结构、DNA模型、生理过程等
"""
from typing import Dict, Any, List

from .base_renderer import BaseComponentRenderer
from ..schemas.animation_schema import (
    ComponentType,
    Point,
    Color,
    CellOrganelle
)


class CellStructureRenderer(BaseComponentRenderer):
    """细胞结构渲染器"""
    
    def __init__(self, position: Point, cell_type: str = "animal",
                 size: int = 200):
        super().__init__()
        self.position = position
        self.cell_type = cell_type
        self.size = size
        self.organelles: List[CellOrganelle] = []
        self.show_membrane = True
        self.show_nucleus = True
        self.interactive_labels = True
        self._init_organelles()
    
    def _init_organelles(self):
        """初始化细胞器"""
        center_x = self.position.x
        center_y = self.position.y
        
        if self.cell_type == "animal":
            self.organelles = [
                CellOrganelle("细胞核", Point(center_x, center_y), 50, 
                             Color(147, 51, 234, 0.8), 
                             "控制细胞的遗传和代谢活动"),
                CellOrganelle("线粒体", Point(center_x + 60, center_y - 30), 30,
                             Color(234, 88, 12, 0.8),
                             "细胞的能量工厂，进行呼吸作用"),
                CellOrganelle("内质网", Point(center_x - 70, center_y), 40,
                             Color(59, 130, 246, 0.8),
                             "蛋白质和脂质的合成与运输"),
                CellOrganelle("高尔基体", Point(center_x + 50, center_y + 50), 35,
                             Color(168, 85, 247, 0.8),
                             "加工、分类和运输蛋白质"),
            ]
        else:
            self.organelles = [
                CellOrganelle("细胞核", Point(center_x, center_y + 20), 45,
                             Color(147, 51, 234, 0.8),
                             "控制细胞的遗传和代谢活动"),
                CellOrganelle("叶绿体", Point(center_x - 60, center_y - 40), 40,
                             Color(34, 197, 94, 0.8),
                             "进行光合作用，将光能转化为化学能"),
                CellOrganelle("液泡", Point(center_x + 50, center_y), 50,
                             Color(56, 189, 248, 0.6),
                             "储存水分和营养物质"),
                CellOrganelle("线粒体", Point(center_x - 40, center_y + 50), 25,
                             Color(234, 88, 12, 0.8),
                             "细胞的能量工厂"),
            ]
    
    def get_component_type(self) -> ComponentType:
        return ComponentType.CELL_STRUCTURE
    
    def render(self, canvas_width: int = 800, canvas_height: int = 600) -> Dict[str, Any]:
        return {
            "id": self.component_id,
            "type": self.get_component_type().value,
            "position": {"x": self.position.x, "y": self.position.y},
            "cellType": self.cell_type,
            "size": self.size,
            "organelles": [
                {
                    "name": o.name,
                    "position": {"x": o.position.x, "y": o.position.y},
                    "size": o.size,
                    "color": o.color.to_rgba(),
                    "description": o.description
                }
                for o in self.organelles
            ],
            "showMembrane": self.show_membrane,
            "showNucleus": self.show_nucleus,
            "interactiveLabels": self.interactive_labels
        }
    
    def generate_js_code(self) -> str:
        organelles_js = []
        for i, org in enumerate(self.organelles):
            organelles_js.append(f"""
            {{
                name: '{org.name}',
                x: {org.position.x},
                y: {org.position.y},
                size: {org.size},
                color: 'rgba({org.color.r}, {org.color.g}, {org.color.b}, {org.color.a})',
                description: '{org.description}'
            }}
            """)
        
        membrane_color = "rgba(56, 189, 248, 0.6)" if self.cell_type == "plant" else "rgba(148, 163, 184, 0.8)"
        
        return f"""
        // 绘制细胞结构
        function drawCellStructure(time) {{
            const organelles = [{', '.join(organelles_js)}];
            const centerX = {self.position.x};
            const centerY = {self.position.y};
            const size = {self.size};
            const cellType = '{self.cell_type}';
            
            // 绘制细胞膜/细胞壁
            ctx.save();
            ctx.translate(centerX, centerY);
            
            // 呼吸动画效果
            const breathe = 1 + Math.sin(time * 2) * 0.02;
            ctx.scale(breathe, breathe);
            
            // 植物细胞：细胞壁 + 细胞膜
            if (cellType === 'plant') {{
                ctx.beginPath();
                ctx.rect(-size, -size, size * 2, size * 2);
                ctx.fillStyle = 'rgba(34, 197, 94, 0.2)';
                ctx.fill();
                ctx.strokeStyle = 'rgba(34, 197, 94, 0.8)';
                ctx.lineWidth = 4;
                ctx.stroke();
                
                ctx.beginPath();
                ctx.rect(-size * 0.9, -size * 0.9, size * 1.8, size * 1.8);
                ctx.fillStyle = 'rgba(15, 23, 42, 0.9)';
                ctx.fill();
                ctx.strokeStyle = '{membrane_color}';
                ctx.lineWidth = 2;
                ctx.stroke();
            }} else {{
                // 动物细胞：圆形细胞膜
                ctx.beginPath();
                ctx.arc(0, 0, size, 0, Math.PI * 2);
                ctx.fillStyle = 'rgba(15, 23, 42, 0.9)';
                ctx.fill();
                ctx.strokeStyle = '{membrane_color}';
                ctx.lineWidth = 3;
                ctx.stroke();
                
                // 细胞质效果
                ctx.beginPath();
                ctx.arc(0, 0, size - 5, 0, Math.PI * 2);
                ctx.fillStyle = 'rgba(30, 41, 59, 0.5)';
                ctx.fill();
            }}
            
            ctx.restore();
            
            // 绘制细胞器
            organelles.forEach((org, index) => {{
                const pulse = 1 + Math.sin(time * 3 + index) * 0.05;
                
                ctx.save();
                ctx.translate(org.x, org.y);
                ctx.scale(pulse, pulse);
                
                // 细胞器形状
                ctx.beginPath();
                if (org.name === '线粒体') {{
                    // 椭圆形
                    ctx.ellipse(0, 0, org.size, org.size * 0.6, 0, 0, Math.PI * 2);
                }} else if (org.name === '内质网') {{
                    // 网状
                    ctx.ellipse(0, 0, org.size, org.size * 0.4, Math.PI / 6, 0, Math.PI * 2);
                }} else if (org.name === '液泡') {{
                    ctx.arc(0, 0, org.size, 0, Math.PI * 2);
                }} else {{
                    ctx.arc(0, 0, org.size, 0, Math.PI * 2);
                }}
                
                ctx.fillStyle = org.color;
                ctx.fill();
                ctx.strokeStyle = org.color.replace(/[\\d\\.]+\\)$/, '1)');
                ctx.lineWidth = 2;
                ctx.stroke();
                
                ctx.restore();
                
                // 标签
                ctx.fillStyle = '#e2e8f0';
                ctx.font = '12px Microsoft YaHei';
                ctx.textAlign = 'center';
                ctx.fillText(org.name, org.x, org.y + org.size + 15);
            }});
        }}
        """


class DNAModelRenderer(BaseComponentRenderer):
    """DNA模型渲染器"""
    
    def __init__(self, position: Point, height: int = 300):
        super().__init__()
        self.position = position
        self.height = height
        self.width = 100
        self.rotate_speed = 1.0
        self.show_labels = True
    
    def get_component_type(self) -> ComponentType:
        return ComponentType.DNA_MODEL
    
    def render(self, canvas_width: int = 800, canvas_height: int = 600) -> Dict[str, Any]:
        return {
            "id": self.component_id,
            "type": self.get_component_type().value,
            "position": {"x": self.position.x, "y": self.position.y},
            "height": self.height,
            "width": self.width,
            "rotateSpeed": self.rotate_speed,
            "showLabels": self.show_labels
        }
    
    def generate_js_code(self) -> str:
        return f"""
        // 绘制DNA双螺旋模型
        function drawDNAModel(time) {{
            const centerX = {self.position.x};
            const centerY = {self.position.y};
            const height = {self.height};
            const width = {self.width};
            
            const basePairs = 20;
            const pairSpacing = height / basePairs;
            
            ctx.save();
            ctx.translate(centerX, centerY - height / 2);
            
            // 绘制碱基对和骨架
            for (let i = 0; i < basePairs; i++) {{
                const y = i * pairSpacing;
                const progress = i / basePairs;
                const rotation = time * {self.rotate_speed} + progress * Math.PI * 4;
                
                const offset = Math.cos(rotation) * width / 2;
                const offset2 = Math.cos(rotation + Math.PI) * width / 2;
                
                // 左链骨架
                ctx.beginPath();
                ctx.arc(-offset, y, 8, 0, Math.PI * 2);
                ctx.fillStyle = 'rgba(56, 189, 248, 0.9)';
                ctx.fill();
                
                // 右链骨架
                ctx.beginPath();
                ctx.arc(offset, y, 8, 0, Math.PI * 2);
                ctx.fillStyle = 'rgba(244, 114, 182, 0.9)';
                ctx.fill();
                
                // 碱基对连接
                const baseType = i % 4;
                const baseColors = [
                    'rgba(34, 197, 94, 0.8)',   // A
                    'rgba(234, 179, 8, 0.8)',   // T
                    'rgba(168, 85, 247, 0.8)',  // G
                    'rgba(249, 115, 22, 0.8)'   // C
                ];
                
                ctx.beginPath();
                ctx.moveTo(-offset, y);
                ctx.lineTo(offset, y);
                ctx.strokeStyle = baseColors[baseType];
                ctx.lineWidth = 4;
                ctx.stroke();
            }}
            
            // 绘制螺旋连线（骨架）
            ctx.beginPath();
            for (let t = 0; t < Math.PI * 4 + 0.1; t += 0.1) {{
                const y = (t / (Math.PI * 4)) * height;
                const x = Math.cos(t + time * {self.rotate_speed}) * width / 2;
                if (t === 0) {{
                    ctx.moveTo(-x, y);
                }} else {{
                    ctx.lineTo(-x, y);
                }}
            }}
            ctx.strokeStyle = 'rgba(56, 189, 248, 0.5)';
            ctx.lineWidth = 3;
            ctx.stroke();
            
            ctx.beginPath();
            for (let t = 0; t < Math.PI * 4 + 0.1; t += 0.1) {{
                const y = (t / (Math.PI * 4)) * height;
                const x = Math.cos(t + time * {self.rotate_speed} + Math.PI) * width / 2;
                if (t === 0) {{
                    ctx.moveTo(-x, y);
                }} else {{
                    ctx.lineTo(-x, y);
                }}
            }}
            ctx.strokeStyle = 'rgba(244, 114, 182, 0.5)';
            ctx.lineWidth = 3;
            ctx.stroke();
            
            ctx.restore();
            
            // 标签
            ctx.fillStyle = '#e2e8f0';
            ctx.font = '14px Microsoft YaHei';
            ctx.textAlign = 'center';
            ctx.fillText('DNA双螺旋结构', centerX, centerY + height / 2 + 30);
        }}
        """


class CellDivisionRenderer(BaseComponentRenderer):
    """细胞分裂过程渲染器"""
    
    def __init__(self, position: Point, size: int = 150):
        super().__init__()
        self.position = position
        self.size = size
        self.stages = [
            "间期", "前期", "中期", "后期", "末期", "胞质分裂"
        ]
    
    def get_component_type(self) -> ComponentType:
        return ComponentType.PHYSIOLOGICAL_PROCESS
    
    def render(self, canvas_width: int = 800, canvas_height: int = 600) -> Dict[str, Any]:
        return {
            "id": self.component_id,
            "type": self.get_component_type().value,
            "position": {"x": self.position.x, "y": self.position.y},
            "size": self.size,
            "stages": self.stages
        }
    
    def generate_js_code(self) -> str:
        return f"""
        // 绘制细胞分裂过程
        function drawCellDivision(time) {{
            const centerX = {self.position.x};
            const centerY = {self.position.y};
            const size = {self.size};
            
            // 计算当前阶段
            const stageDuration = 3;
            const totalDuration = stageDuration * 6;
            const cycleTime = time % totalDuration;
            const currentStage = Math.floor(cycleTime / stageDuration);
            const stageProgress = (cycleTime % stageDuration) / stageDuration;
            
            const stages = {self.stages};
            
            ctx.save();
            ctx.translate(centerX, centerY);
            
            // 根据阶段绘制不同内容
            switch(currentStage) {{
                case 0: // 间期
                    drawInterphase(size, stageProgress);
                    break;
                case 1: // 前期
                    drawProphase(size, stageProgress);
                    break;
                case 2: // 中期
                    drawMetaphase(size, stageProgress);
                    break;
                case 3: // 后期
                    drawAnaphase(size, stageProgress);
                    break;
                case 4: // 末期
                    drawTelophase(size, stageProgress);
                    break;
                case 5: // 胞质分裂
                    drawCytokinesis(size, stageProgress);
                    break;
            }}
            
            ctx.restore();
            
            // 阶段标签
            ctx.fillStyle = '#e2e8f0';
            ctx.font = 'bold 16px Microsoft YaHei';
            ctx.textAlign = 'center';
            ctx.fillText(stages[currentStage], centerX, centerY + size + 40);
            
            // 进度指示器
            ctx.font = '12px Microsoft YaHei';
            ctx.fillStyle = '#94a3b8';
            for (let i = 0; i < 6; i++) {{
                const x = centerX - 100 + i * 40;
                const y = centerY + size + 60;
                ctx.beginPath();
                ctx.arc(x, y, 6, 0, Math.PI * 2);
                ctx.fillStyle = i <= currentStage ? 'rgba(56, 189, 248, 0.8)' : 'rgba(148, 163, 184, 0.3)';
                ctx.fill();
            }}
        }}
        
        function drawInterphase(size, progress) {{
            // 细胞核
            ctx.beginPath();
            ctx.arc(0, 0, size * 0.8, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(30, 41, 59, 0.9)';
            ctx.fill();
            ctx.strokeStyle = 'rgba(148, 163, 184, 0.8)';
            ctx.lineWidth = 3;
            ctx.stroke();
            
            // 染色质
            for (let i = 0; i < 20; i++) {{
                const angle = (i / 20) * Math.PI * 2 + progress;
                const r = size * 0.4 + Math.sin(i * 2) * size * 0.1;
                ctx.beginPath();
                ctx.arc(Math.cos(angle) * r, Math.sin(angle) * r, 5, 0, Math.PI * 2);
                ctx.fillStyle = 'rgba(147, 51, 234, 0.6)';
                ctx.fill();
            }}
            
            // 核仁
            ctx.beginPath();
            ctx.arc(0, 0, size * 0.2, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(147, 51, 234, 0.8)';
            ctx.fill();
        }}
        
        function drawProphase(size, progress) {{
            ctx.beginPath();
            ctx.arc(0, 0, size * 0.8, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(30, 41, 59, 0.9)';
            ctx.fill();
            ctx.strokeStyle = 'rgba(148, 163, 184, 0.8)';
            ctx.lineWidth = 3;
            ctx.stroke();
            
            // 染色体凝缩
            for (let i = 0; i < 4; i++) {{
                const angle = (i / 4) * Math.PI * 2 + progress;
                const r = size * 0.3;
                ctx.save();
                ctx.translate(Math.cos(angle) * r, Math.sin(angle) * r);
                ctx.rotate(angle);
                ctx.fillStyle = 'rgba(147, 51, 234, 0.9)';
                ctx.fillRect(-8 * progress, -25 * progress, 16 * progress, 50 * progress);
                ctx.restore();
            }}
            
            // 核仁消失动画
            ctx.globalAlpha = 1 - progress;
            ctx.beginPath();
            ctx.arc(0, 0, size * 0.2 * (1 - progress * 0.5), 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(147, 51, 234, 0.8)';
            ctx.fill();
            ctx.globalAlpha = 1;
        }}
        
        function drawMetaphase(size, progress) {{
            ctx.beginPath();
            ctx.arc(0, 0, size * 0.8, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(30, 41, 59, 0.9)';
            ctx.fill();
            ctx.strokeStyle = 'rgba(148, 163, 184, 0.8)';
            ctx.lineWidth = 3;
            ctx.stroke();
            
            // 赤道板
            ctx.beginPath();
            ctx.moveTo(-size * 0.7, 0);
            ctx.lineTo(size * 0.7, 0);
            ctx.strokeStyle = 'rgba(239, 68, 68, 0.3)';
            ctx.setLineDash([5, 5]);
            ctx.lineWidth = 2;
            ctx.stroke();
            ctx.setLineDash([]);
            
            // 染色体排列在赤道板
            for (let i = 0; i < 4; i++) {{
                const x = (i - 1.5) * 30;
                ctx.save();
                ctx.translate(x, 0);
                ctx.fillStyle = 'rgba(147, 51, 234, 0.9)';
                ctx.fillRect(-8, -25, 16, 50);
                ctx.restore();
            }}
            
            // 纺锤丝
            for (let i = 0; i < 8; i++) {{
                ctx.beginPath();
                ctx.moveTo((i - 3.5) * 30, 0);
                ctx.lineTo(-size * 0.7, (i - 3.5) * 10);
                ctx.strokeStyle = 'rgba(148, 163, 184, 0.5)';
                ctx.lineWidth = 1;
                ctx.stroke();
            }}
        }}
        
        function drawAnaphase(size, progress) {{
            ctx.beginPath();
            ctx.arc(0, 0, size * 0.8, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(30, 41, 59, 0.9)';
            ctx.fill();
            ctx.strokeStyle = 'rgba(148, 163, 184, 0.8)';
            ctx.lineWidth = 3;
            ctx.stroke();
            
            // 姐妹染色单体分离
            const moveDistance = progress * size * 0.5;
            
            for (let i = 0; i < 4; i++) {{
                const x = (i - 1.5) * 30;
                // 向上移动
                ctx.fillStyle = 'rgba(147, 51, 234, 0.9)';
                ctx.fillRect(x - 8, -25 - moveDistance, 16, 45);
                // 向下移动
                ctx.fillStyle = 'rgba(56, 189, 248, 0.9)';
                ctx.fillRect(x - 8, 5 + moveDistance, 16, 45);
            }}
        }}
        
        function drawTelophase(size, progress) {{
            const moveDistance = size * 0.5;
            
            // 两个子细胞核形成
            ctx.beginPath();
            ctx.arc(0, -moveDistance, size * 0.5, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(30, 41, 59, 0.9)';
            ctx.fill();
            ctx.strokeStyle = 'rgba(148, 163, 184, 0.8)';
            ctx.lineWidth = 3;
            ctx.stroke();
            
            ctx.beginPath();
            ctx.arc(0, moveDistance, size * 0.5, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(30, 41, 59, 0.9)';
            ctx.fill();
            ctx.strokeStyle = 'rgba(148, 163, 184, 0.8)';
            ctx.lineWidth = 3;
            ctx.stroke();
            
            // 染色体解旋
            for (let pole = -1; pole <= 1; pole += 2) {{
                for (let i = 0; i < 4; i++) {{
                    const x = (i - 1.5) * 20;
                    ctx.fillStyle = 'rgba(147, 51, 234, 0.7)';
                    ctx.beginPath();
                    ctx.arc(x, pole * moveDistance, 8 * (1 - progress * 0.5), 0, Math.PI * 2);
                    ctx.fill();
                }}
            }}
        }}
        
        function drawCytokinesis(size, progress) {{
            const moveDistance = size * 0.5;
            const separation = progress * size * 0.3;
            
            // 两个子细胞
            ctx.beginPath();
            ctx.arc(-separation, -moveDistance, size * 0.45, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(30, 41, 59, 0.9)';
            ctx.fill();
            ctx.strokeStyle = 'rgba(56, 189, 248, 0.8)';
            ctx.lineWidth = 3;
            ctx.stroke();
            
            ctx.beginPath();
            ctx.arc(separation, moveDistance, size * 0.45, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(30, 41, 59, 0.9)';
            ctx.fill();
            ctx.strokeStyle = 'rgba(244, 114, 182, 0.8)';
            ctx.lineWidth = 3;
            ctx.stroke();
            
            // 细胞核
            ctx.fillStyle = 'rgba(147, 51, 234, 0.8)';
            ctx.beginPath();
            ctx.arc(-separation, -moveDistance, size * 0.15, 0, Math.PI * 2);
            ctx.fill();
            ctx.beginPath();
            ctx.arc(separation, moveDistance, size * 0.15, 0, Math.PI * 2);
            ctx.fill();
        }}
        """


def create_cell_demo(position: Point, cell_type: str = "animal") -> List[str]:
    """创建细胞演示"""
    cell = CellStructureRenderer(position, cell_type)
    
    return [
        cell.generate_js_code(),
        """
        function renderScene(time) {
            drawCellStructure(time);
        }
        """
    ]


def create_dna_demo(position: Point) -> List[str]:
    """创建DNA演示"""
    dna = DNAModelRenderer(position)
    
    return [
        dna.generate_js_code(),
        """
        function renderScene(time) {
            drawDNAModel(time);
        }
        """
    ]


def create_cell_division_demo(position: Point) -> List[str]:
    """创建细胞分裂演示"""
    division = CellDivisionRenderer(position)
    
    return [
        division.generate_js_code(),
        """
        function renderScene(time) {
            drawCellDivision(time);
        }
        """
    ]
