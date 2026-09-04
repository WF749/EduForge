"""
动画系统模块
分层架构：数据层 -> 内容解析层 -> 动画引擎层 -> 组件渲染层
"""

from .schemas.animation_schema import (
    SubjectType,
    ComponentType,
    AnimationType,
    EasingType,
    Point,
    Color,
    AnimationEffect,
    BaseComponent,
    KnowledgePoint,
    Scene,
    SceneComponent,
    AnimationProject,
    ContentAnalysisResult,
    COLOR_SCHEMES,
    SUBJECT_KEYWORDS
)

from .engines.content_parser import (
    ContentParser,
    content_parser
)

from .engines.animation_engine import (
    AnimationGenerationEngine,
    animation_engine
)

from .components.base_renderer import (
    BaseComponentRenderer,
    ShapeRenderer,
    CircleRenderer,
    RectangleRenderer,
    TextRenderer,
    ArrowRenderer,
    ComponentLibrary,
    component_library,
    generate_canvas_wrapper
)

from .components.math_components import (
    CoordinateSystemRenderer,
    FunctionGraphRenderer,
    GeometricShapeRenderer,
    create_parabola_demo,
    create_triangle_geometry_demo
)

from .components.bio_components import (
    CellStructureRenderer,
    DNAModelRenderer,
    CellDivisionRenderer,
    create_cell_demo,
    create_dna_demo,
    create_cell_division_demo
)

__all__ = [
    # Schemas
    'SubjectType',
    'ComponentType',
    'AnimationType',
    'EasingType',
    'Point',
    'Color',
    'AnimationEffect',
    'BaseComponent',
    'KnowledgePoint',
    'Scene',
    'SceneComponent',
    'AnimationProject',
    'ContentAnalysisResult',
    'COLOR_SCHEMES',
    'SUBJECT_KEYWORDS',
    
    # Engines
    'ContentParser',
    'content_parser',
    'AnimationGenerationEngine',
    'animation_engine',
    
    # Components
    'BaseComponentRenderer',
    'ShapeRenderer',
    'CircleRenderer',
    'RectangleRenderer',
    'TextRenderer',
    'ArrowRenderer',
    'ComponentLibrary',
    'component_library',
    'generate_canvas_wrapper',
    'CoordinateSystemRenderer',
    'FunctionGraphRenderer',
    'GeometricShapeRenderer',
    'create_parabola_demo',
    'create_triangle_geometry_demo',
    'CellStructureRenderer',
    'DNAModelRenderer',
    'CellDivisionRenderer',
    'create_cell_demo',
    'create_dna_demo',
    'create_cell_division_demo',
]

__version__ = '1.0.0'
