"""
标准化动画场景描述格式 (JSON Schema)
核心数据格式层 - 定义所有动画组件的数据结构
"""
from typing import List, Dict, Optional, Any, Literal, Union
from dataclasses import dataclass, field
from enum import Enum


class SubjectType(str, Enum):
    """学科类型枚举"""
    MATHEMATICS = "mathematics"
    PHYSICS = "physics"
    CHEMISTRY = "chemistry"
    BIOLOGY = "biology"
    GEOGRAPHY = "geography"
    HISTORY = "history"
    CHINESE = "chinese"
    ENGLISH = "english"
    GENERAL = "general"


class ComponentType(str, Enum):
    """动画组件类型枚举"""
    # 基础图形
    CIRCLE = "circle"
    RECTANGLE = "rectangle"
    TRIANGLE = "triangle"
    LINE = "line"
    ARROW = "arrow"
    TEXT = "text"
    
    # 数学组件
    COORDINATE_SYSTEM = "coordinate_system"
    FUNCTION_GRAPH = "function_graph"
    GEOMETRIC_SHAPE = "geometric_shape"
    
    # 物理组件
    MOTION_TRAJECTORY = "motion_trajectory"
    FORCE_DIAGRAM = "force_diagram"
    CIRCUIT_DIAGRAM = "circuit_diagram"
    
    # 化学组件
    MOLECULE_STRUCTURE = "molecule_structure"
    REACTION_PROCESS = "reaction_process"
    
    # 生物组件
    CELL_STRUCTURE = "cell_structure"
    DNA_MODEL = "dna_model"
    PHYSIOLOGICAL_PROCESS = "physiological_process"
    
    # 通用组件
    TIMELINE = "timeline"
    FLOW_CHART = "flow_chart"
    IMAGE = "image"


class AnimationType(str, Enum):
    """动画效果类型"""
    NONE = "none"
    FADE = "fade"
    SLIDE = "slide"
    SCALE = "scale"
    ROTATE = "rotate"
    PATH = "path"
    MORPH = "morph"
    PARTICLE = "particle"


class EasingType(str, Enum):
    """缓动函数类型"""
    LINEAR = "linear"
    EASE_IN = "ease_in"
    EASE_OUT = "ease_out"
    EASE_IN_OUT = "ease_in_out"
    BOUNCE = "bounce"
    ELASTIC = "elastic"


@dataclass
class Point:
    """坐标点"""
    x: float
    y: float


@dataclass
class Color:
    """颜色"""
    r: int
    g: int
    b: int
    a: float = 1.0
    
    def to_hex(self) -> str:
        return f"#{self.r:02x}{self.g:02x}{self.b:02x}"
    
    def to_rgba(self) -> str:
        return f"rgba({self.r}, {self.g}, {self.b}, {self.a})"


@dataclass
class AnimationEffect:
    """动画效果"""
    type: AnimationType
    duration: float = 1.0
    delay: float = 0.0
    easing: EasingType = EasingType.EASE_IN_OUT
    repeat: int = 0
    direction: str = "normal"
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BaseComponent:
    """基础组件"""
    id: str
    type: ComponentType
    name: str = ""
    description: str = ""
    position: Point = field(default_factory=lambda: Point(0, 0))
    rotation: float = 0.0
    scale: float = 1.0
    visible: bool = True
    opacity: float = 1.0
    z_index: int = 0
    animation: Optional[AnimationEffect] = None
    interactive: bool = False
    click_action: Optional[str] = None
    style: Dict[str, Any] = field(default_factory=dict)
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TextComponent(BaseComponent):
    """文本组件"""
    text: str = ""
    font_size: int = 16
    font_family: str = "Microsoft YaHei"
    color: Color = field(default_factory=lambda: Color(255, 255, 255))
    align: str = "center"
    bold: bool = False


@dataclass
class MathFunctionComponent(BaseComponent):
    """数学函数图像组件"""
    expression: str = ""
    x_min: float = -10
    x_max: float = 10
    y_min: float = -10
    y_max: float = 10
    line_width: int = 2
    line_color: Color = field(default_factory=lambda: Color(56, 189, 248))
    show_grid: bool = True
    show_axis: bool = True


@dataclass
class CoordinateSystemComponent(BaseComponent):
    """坐标系组件"""
    width: int = 400
    height: int = 300
    x_min: float = -10
    x_max: float = 10
    y_min: float = -10
    y_max: float = 10
    x_label: str = "x"
    y_label: str = "y"
    grid_color: Color = field(default_factory=lambda: Color(100, 100, 100, 0.3))
    axis_color: Color = field(default_factory=lambda: Color(200, 200, 200))


@dataclass
class MoleculeAtom:
    """分子中的原子"""
    element: str
    position: Point
    color: Color
    radius: int = 20


@dataclass
class MoleculeBond:
    """化学键"""
    atom1: int
    atom2: int
    type: int = 1


@dataclass
class MoleculeComponent(BaseComponent):
    """分子结构组件"""
    atoms: List[MoleculeAtom] = field(default_factory=list)
    bonds: List[MoleculeBond] = field(default_factory=list)
    show_labels: bool = True
    rotate_animation: bool = False


@dataclass
class CellOrganelle:
    """细胞器"""
    name: str
    position: Point
    size: int
    color: Color
    description: str = ""


@dataclass
class CellComponent(BaseComponent):
    """细胞结构组件"""
    cell_type: str = "animal"
    organelles: List[CellOrganelle] = field(default_factory=list)
    show_membrane: bool = True
    show_nucleus: bool = True
    interactive_labels: bool = True


@dataclass
class KnowledgePoint:
    """知识点"""
    id: str
    name: str
    description: str = ""
    subject: SubjectType = SubjectType.GENERAL
    difficulty: int = 1
    related_concepts: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    visual_hints: List[str] = field(default_factory=list)


@dataclass
class SceneComponent:
    """场景中的组件实例"""
    component_id: str
    start_time: float = 0.0
    end_time: float = 10.0
    entrance_animation: Optional[AnimationEffect] = None
    exit_animation: Optional[AnimationEffect] = None
    emphasis_points: List[float] = field(default_factory=list)
    annotations: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Scene:
    """动画场景"""
    id: str
    title: str
    description: str = ""
    duration: float = 10.0
    components: List[SceneComponent] = field(default_factory=list)
    narration: str = ""
    key_points: List[str] = field(default_factory=list)
    background_color: Color = field(default_factory=lambda: Color(15, 23, 42))
    auto_advance: bool = True
    pause_points: List[float] = field(default_factory=list)


@dataclass
class AnimationProject:
    """完整动画项目"""
    id: str
    title: str
    subject: SubjectType = SubjectType.GENERAL
    audience: str = ""
    description: str = ""
    total_duration: float = 60.0
    scenes: List[Scene] = field(default_factory=list)
    knowledge_points: List[KnowledgePoint] = field(default_factory=list)
    style: Dict[str, Any] = field(default_factory=dict)
    version: str = "1.0"
    created_at: str = ""
    updated_at: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        import json
        from dataclasses import asdict
        return asdict(self)
    
    def to_json(self, indent: int = 2) -> str:
        """转换为JSON字符串"""
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


@dataclass
class ContentAnalysisResult:
    """内容分析结果"""
    subject: SubjectType = SubjectType.GENERAL
    knowledge_points: List[KnowledgePoint] = field(default_factory=list)
    suggested_scenes: List[Dict[str, Any]] = field(default_factory=list)
    recommended_components: List[ComponentType] = field(default_factory=list)
    key_concepts: List[str] = field(default_factory=list)
    difficulty_level: int = 1
    target_audience: str = ""


# 预定义颜色方案
COLOR_SCHEMES = {
    "modern": {
        "primary": Color(56, 189, 248),
        "secondary": Color(167, 139, 250),
        "accent": Color(244, 114, 182),
        "success": Color(52, 211, 153),
        "warning": Color(251, 146, 60),
        "error": Color(248, 113, 113),
        "background": Color(15, 23, 42),
        "surface": Color(30, 41, 59),
        "text": Color(226, 232, 240),
        "text_secondary": Color(148, 163, 184),
    },
    "warm": {
        "primary": Color(251, 191, 36),
        "secondary": Color(249, 115, 22),
        "accent": Color(239, 68, 68),
        "success": Color(34, 197, 94),
        "warning": Color(234, 179, 8),
        "error": Color(239, 68, 68),
        "background": Color(30, 20, 10),
        "surface": Color(41, 37, 36),
        "text": Color(254, 243, 199),
        "text_secondary": Color(168, 162, 158),
    },
    "nature": {
        "primary": Color(34, 197, 94),
        "secondary": Color(16, 185, 129),
        "accent": Color(6, 182, 212),
        "success": Color(34, 197, 94),
        "warning": Color(234, 179, 8),
        "error": Color(239, 68, 68),
        "background": Color(5, 46, 22),
        "surface": Color(20, 83, 45),
        "text": Color(220, 252, 231),
        "text_secondary": Color(134, 239, 172),
    }
}


# 学科关键词映射
SUBJECT_KEYWORDS = {
    SubjectType.MATHEMATICS: [
        "数学", "函数", "方程", "几何", "代数", "微积分", "概率", "统计",
        "三角形", "圆", "向量", "矩阵", "导数", "积分", "坐标系", "公式"
    ],
    SubjectType.PHYSICS: [
        "物理", "力学", "运动", "力", "能量", "电磁", "光学", "热学",
        "速度", "加速度", "牛顿", "动量", "动能", "势能", "电路", "磁场"
    ],
    SubjectType.CHEMISTRY: [
        "化学", "分子", "原子", "元素", "反应", "化学键", "有机", "无机",
        "氧化", "还原", "溶液", "酸碱", "周期表", "电子", "离子"
    ],
    SubjectType.BIOLOGY: [
        "生物", "细胞", "DNA", "基因", "遗传", "进化", "生态", "生理",
        "分裂", "繁殖", "光合作用", "呼吸作用", "消化系统", "神经系统"
    ],
    SubjectType.GEOGRAPHY: [
        "地理", "地球", "气候", "地形", "板块", "地图", "气候", "水文",
        "山脉", "河流", "海洋", "大气", "板块运动", "经纬度"
    ],
    SubjectType.HISTORY: [
        "历史", "朝代", "战争", "革命", "文明", "古代", "近代", "现代",
        "事件", "人物", "年代", "世纪", "文化", "政治", "经济"
    ],
    SubjectType.CHINESE: [
        "语文", "文学", "诗歌", "文言文", "现代文", "作文", "阅读", "语法",
        "诗词", "散文", "小说", "戏剧", "修辞", "成语", "典故"
    ],
    SubjectType.ENGLISH: [
        "英语", "词汇", "语法", "阅读", "听力", "口语", "写作", "翻译",
        "时态", "语态", "从句", "单词", "短语", "句型", "发音"
    ],
}
