"""
动画生成引擎
功能：根据内容分析结果，编排场景，生成时间轴，组合组件
输入：内容分析结果 + 知识点列表
输出：完整动画项目 + HTML渲染文件
"""
import os
import uuid
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

from ..schemas.animation_schema import (
    SubjectType,
    ContentAnalysisResult,
    AnimationProject,
    Scene,
    KnowledgePoint,
    Point,
    Color,
    SceneComponent
)
from ..components.base_renderer import generate_canvas_wrapper
from ..components.math_components import (
    CoordinateSystemRenderer,
    FunctionGraphRenderer,
    GeometricShapeRenderer,
    create_parabola_demo,
    create_triangle_geometry_demo
)
from ..components.bio_components import (
    CellStructureRenderer,
    DNAModelRenderer,
    CellDivisionRenderer,
    create_cell_demo,
    create_dna_demo,
    create_cell_division_demo
)


class AnimationGenerationEngine:
    """动画生成引擎 - 协调各模块生成完整动画"""
    
    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or "generated_animations"
        self._ensure_output_dir()
    
    def _ensure_output_dir(self):
        """确保输出目录存在"""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)
    
    def generate_animation_project(self, analysis_result: ContentAnalysisResult,
                                   topic: str, audience: str = "") -> AnimationProject:
        """生成动画项目"""
        project_id = f"anim_{uuid.uuid4().hex[:12]}"
        
        # 创建动画项目
        project = AnimationProject(
            id=project_id,
            title=topic,
            subject=analysis_result.subject,
            audience=audience or analysis_result.target_audience,
            description=f"{topic}教学动画",
            total_duration=60.0,
            knowledge_points=analysis_result.knowledge_points,
            style={"theme": "modern"},
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        
        # 生成场景
        scenes = self._generate_scenes(analysis_result, topic)
        project.scenes = scenes
        
        # 计算总时长
        project.total_duration = sum(scene.duration for scene in scenes)
        
        return project
    
    def _generate_scenes(self, analysis_result: ContentAnalysisResult, 
                        topic: str) -> List[Scene]:
        """生成场景列表"""
        scenes = []
        
        # 场景1：引入场景
        intro_scene = self._create_intro_scene(topic, analysis_result.subject)
        scenes.append(intro_scene)
        
        # 中间场景：每个知识点一个场景
        for i, kp in enumerate(analysis_result.knowledge_points[:4]):
            scene = self._create_knowledge_scene(kp, analysis_result.subject, i + 1)
            scenes.append(scene)
        
        # 最后场景：总结
        summary_scene = self._create_summary_scene(topic, analysis_result.knowledge_points)
        scenes.append(summary_scene)
        
        return scenes
    
    def _create_intro_scene(self, topic: str, subject: SubjectType) -> Scene:
        """创建引入场景"""
        scene_id = f"scene_intro_{uuid.uuid4().hex[:6]}"
        
        return Scene(
            id=scene_id,
            title=f"{topic} - 课程介绍",
            description=f"介绍{topic}的学习目标和重要性",
            duration=8.0,
            narration=f"今天我们来学习{topic}",
            key_points=["背景介绍", "学习目标"],
            background_color=Color(15, 23, 42),
            auto_advance=True
        )
    
    def _create_knowledge_scene(self, kp: KnowledgePoint, 
                               subject: SubjectType, index: int) -> Scene:
        """创建知识点场景"""
        scene_id = f"scene_kp_{uuid.uuid4().hex[:6]}"
        
        return Scene(
            id=scene_id,
            title=kp.name,
            description=kp.description,
            duration=10.0,
            narration=f"接下来讲解{kp.name}",
            key_points=[kp.name] + kp.related_concepts[:2],
            background_color=Color(15, 23, 42),
            auto_advance=True,
            pause_points=[5.0]  # 在5秒处暂停供讲解
        )
    
    def _create_summary_scene(self, topic: str, 
                             knowledge_points: List[KnowledgePoint]) -> Scene:
        """创建总结场景"""
        scene_id = f"scene_summary_{uuid.uuid4().hex[:6]}"
        
        return Scene(
            id=scene_id,
            title="总结回顾",
            description=f"回顾{topic}的核心要点",
            duration=6.0,
            narration="今天的学习内容就到这里，总结一下要点",
            key_points=[kp.name for kp in knowledge_points[:4]],
            background_color=Color(15, 23, 42),
            auto_advance=False
        )
    
    def generate_html_animation(self, project: AnimationProject) -> str:
        """生成HTML动画文件"""
        # 根据学科选择合适的组件演示
        subject = project.subject
        position = Point(400, 300)
        
        # 根据学科生成组件代码
        if subject == SubjectType.MATHEMATICS:
            components = self._generate_math_components(project)
        elif subject == SubjectType.BIOLOGY:
            components = self._generate_biology_components(project)
        elif subject == SubjectType.PHYSICS:
            components = self._generate_physics_components(project)
        elif subject == SubjectType.CHEMISTRY:
            components = self._generate_chemistry_components(project)
        else:
            components = self._generate_general_components(project)
        
        # 生成包装HTML
        html_content = generate_canvas_wrapper(
            components,
            title=project.title,
            width=800,
            height=600
        )
        
        return html_content
    
    def _generate_math_components(self, project: AnimationProject) -> List[str]:
        """生成数学组件"""
        position = Point(150, 100)
        
        # 检查是否有函数相关的知识点
        has_function = any("函数" in kp.name or "方程" in kp.name 
                          for kp in project.knowledge_points)
        has_geometry = any("几何" in kp.name or "三角" in kp.name or "图形" in kp.name 
                          for kp in project.knowledge_points)
        
        if has_function:
            return create_parabola_demo(position)
        elif has_geometry:
            return create_triangle_geometry_demo(Point(300, 150))
        else:
            # 默认坐标系演示
            coord = CoordinateSystemRenderer(position, 500, 400, -5, 5, -5, 5)
            func = FunctionGraphRenderer("sin(x)", -5, 5, -2, 2, position, 500, 400,
                                        line_color=Color(167, 139, 250))
            
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
    
    def _generate_biology_components(self, project: AnimationProject) -> List[str]:
        """生成生物组件"""
        position = Point(400, 250)
        
        # 检查知识点关键词
        has_cell = any("细胞" in kp.name for kp in project.knowledge_points)
        has_dna = any("DNA" in kp.name or "基因" in kp.name for kp in project.knowledge_points)
        has_division = any("分裂" in kp.name or "增殖" in kp.name for kp in project.knowledge_points)
        
        if has_division or "分裂" in project.title:
            return create_cell_division_demo(position)
        elif has_dna or "DNA" in project.title:
            return create_dna_demo(position)
        elif has_cell or "细胞" in project.title:
            return create_cell_demo(position, "animal")
        else:
            # 默认DNA演示
            return create_dna_demo(position)
    
    def _generate_physics_components(self, project: AnimationProject) -> List[str]:
        """生成物理组件"""
        position = Point(400, 300)
        
        # 简单的抛物线运动演示
        return self._generate_motion_demo(position)
    
    def _generate_motion_demo(self, position: Point) -> List[str]:
        """生成运动演示"""
        center_x = position.x
        center_y = position.y
        
        return [
            """
            // 绘制抛物运动
            function drawMotionTrajectory(time) {
                const startX = 100;
                const startY = 450;
                const velocity = 200;
                const angle = Math.PI / 4;
                const gravity = 500;
                
                const t = (time * 0.5) % 2;
                
                // 绘制轨迹
                ctx.beginPath();
                ctx.strokeStyle = 'rgba(148, 163, 184, 0.3)';
                ctx.setLineDash([5, 5]);
                for (let tt = 0; tt <= t; tt += 0.02) {
                    const x = startX + velocity * Math.cos(angle) * tt;
                    const y = startY - (velocity * Math.sin(angle) * tt - 0.5 * gravity * tt * tt);
                    if (tt === 0) {
                        ctx.moveTo(x, y);
                    } else {
                        ctx.lineTo(x, y);
                    }
                }
                ctx.stroke();
                ctx.setLineDash([]);
                
                // 绘制物体
                const currentX = startX + velocity * Math.cos(angle) * t;
                const currentY = startY - (velocity * Math.sin(angle) * t - 0.5 * gravity * t * t);
                
                ctx.beginPath();
                ctx.arc(currentX, currentY, 15, 0, Math.PI * 2);
                ctx.fillStyle = 'rgba(56, 189, 248, 0.9)';
                ctx.fill();
                ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)';
                ctx.lineWidth = 2;
                ctx.stroke();
                
                // 绘制速度向量
                const vx = velocity * Math.cos(angle);
                const vy = velocity * Math.sin(angle) - gravity * t;
                
                ctx.beginPath();
                ctx.moveTo(currentX, currentY);
                ctx.lineTo(currentX + vx * 0.3, currentY);
                ctx.strokeStyle = 'rgba(34, 197, 94, 0.8)';
                ctx.lineWidth = 3;
                ctx.stroke();
                
                ctx.beginPath();
                ctx.moveTo(currentX, currentY);
                ctx.lineTo(currentX, currentY - vy * 0.3);
                ctx.strokeStyle = 'rgba(239, 68, 68, 0.8)';
                ctx.stroke();
                
                // 标签
                ctx.fillStyle = '#e2e8f0';
                ctx.font = '14px Microsoft YaHei';
                ctx.fillText('vx (水平速度)', currentX + vx * 0.3 + 10, currentY + 5);
                ctx.fillText('vy (垂直速度)', currentX + 10, currentY - vy * 0.3 - 5);
            }
            
            function renderScene(time) {
                drawMotionTrajectory(time);
            }
            """
        ]
    
    def _generate_chemistry_components(self, project: AnimationProject) -> List[str]:
        """生成化学组件"""
        position = Point(400, 300)
        
        # 简单的分子结构演示
        return self._generate_molecule_demo(position)
    
    def _generate_molecule_demo(self, position: Point) -> List[str]:
        """生成分子结构演示"""
        center_x = position.x
        center_y = position.y
        
        return [
            f"""
            // 绘制水分子H2O
            function drawMolecule(time) {{
                const centerX = {center_x};
                const centerY = {center_y};
                
                // 旋转动画
                const rotation = time * 0.5;
                const cos = Math.cos(rotation);
                const sin = Math.sin(rotation);
                
                function rotatePoint(x, y) {{
                    return {{
                        x: centerX + (x - centerX) * cos - (y - centerY) * sin,
                        y: centerY + (x - centerX) * sin + (y - centerY) * cos
                    }};
                }}
                
                // 原子位置（未旋转）
                const oAtom = {{ x: centerX, y: centerY, r: 35, color: 'rgba(239, 68, 68, 0.9)' }};
                const h1Atom = {{ x: centerX - 50, y: centerY + 40, r: 22, color: 'rgba(255, 255, 255, 0.9)' }};
                const h2Atom = {{ x: centerX + 50, y: centerY + 40, r: 22, color: 'rgba(255, 255, 255, 0.9)' }};
                
                // 绘制化学键
                const oRot = rotatePoint(oAtom.x, oAtom.y);
                const h1Rot = rotatePoint(h1Atom.x, h1Atom.y);
                const h2Rot = rotatePoint(h2Atom.x, h2Atom.y);
                
                ctx.beginPath();
                ctx.moveTo(oRot.x, oRot.y);
                ctx.lineTo(h1Rot.x, h1Rot.y);
                ctx.strokeStyle = 'rgba(148, 163, 184, 0.8)';
                ctx.lineWidth = 6;
                ctx.stroke();
                
                ctx.beginPath();
                ctx.moveTo(oRot.x, oRot.y);
                ctx.lineTo(h2Rot.x, h2Rot.y);
                ctx.stroke();
                
                // 绘制原子
                [
                    {{ ...oAtom, rot: oRot }},
                    {{ ...h1Atom, rot: h1Rot }},
                    {{ ...h2Atom, rot: h2Rot }}
                ].forEach(atom => {{
                    const gradient = ctx.createRadialGradient(
                        atom.rot.x - atom.r * 0.3, atom.rot.y - atom.r * 0.3, 0,
                        atom.rot.x, atom.rot.y, atom.r
                    );
                    gradient.addColorStop(0, 'rgba(255, 255, 255, 0.9)');
                    gradient.addColorStop(0.3, atom.color);
                    gradient.addColorStop(1, atom.color.replace(/[\\d\\.]+\\)$/, '0.6)'));
                    
                    ctx.beginPath();
                    ctx.arc(atom.rot.x, atom.rot.y, atom.r, 0, Math.PI * 2);
                    ctx.fillStyle = gradient;
                    ctx.fill();
                }});
                
                // 标签
                ctx.fillStyle = '#0f172a';
                ctx.font = 'bold 16px Microsoft YaHei';
                ctx.textAlign = 'center';
                ctx.fillText('O', oRot.x, oRot.y + 6);
                ctx.fillStyle = '#0f172a';
                ctx.fillText('H', h1Rot.x, h1Rot.y + 5);
                ctx.fillText('H', h2Rot.x, h2Rot.y + 5);
                
                // 分子式
                ctx.fillStyle = '#e2e8f0';
                ctx.font = 'bold 24px Microsoft YaHei';
                ctx.fillText('H₂O', centerX, centerY + 130);
                ctx.font = '14px Microsoft YaHei';
                ctx.fillText('水分子', centerX, centerY + 155);
            }}
            
            function renderScene(time) {{
                drawMolecule(time);
            }}
            """
        ]
    
    def _generate_general_components(self, project: AnimationProject) -> List[str]:
        """生成通用组件"""
        # 显示知识点标签动画
        kp_names = [kp.name for kp in project.knowledge_points[:6]]
        
        return [
            f"""
            // 通用知识点展示
            function renderScene(time) {{
                const centerX = 400;
                const centerY = 300;
                const keywords = {json.dumps(kp_names, ensure_ascii=False)};
                
                // 绘制中心主题
                ctx.fillStyle = 'rgba(56, 189, 248, 0.9)';
                ctx.font = 'bold 28px Microsoft YaHei';
                ctx.textAlign = 'center';
                ctx.fillText('{project.title}', centerX, centerY - 50);
                
                // 环绕知识点
                keywords.forEach((kp, index) => {{
                    const angle = (index / keywords.length) * Math.PI * 2 + time * 0.3;
                    const radius = 150 + Math.sin(time * 2 + index) * 10;
                    const x = centerX + Math.cos(angle) * radius;
                    const y = centerY + Math.sin(angle) * radius;
                    
                    // 绘制点
                    ctx.beginPath();
                    ctx.arc(x, y, 20, 0, Math.PI * 2);
                    ctx.fillStyle = 'rgba(167, 139, 250, 0.3)';
                    ctx.fill();
                    ctx.strokeStyle = 'rgba(167, 139, 250, 0.8)';
                    ctx.lineWidth = 2;
                    ctx.stroke();
                    
                    // 连线
                    ctx.beginPath();
                    ctx.moveTo(centerX, centerY - 30);
                    ctx.lineTo(x, y);
                    ctx.strokeStyle = 'rgba(148, 163, 184, 0.2)';
                    ctx.lineWidth = 1;
                    ctx.stroke();
                    
                    // 文字
                    ctx.fillStyle = '#e2e8f0';
                    ctx.font = '12px Microsoft YaHei';
                    ctx.fillText(kp.substring(0, 8), x, y + 4);
                }});
                
                // 装饰性粒子
                for (let i = 0; i < 20; i++) {{
                    const px = centerX + Math.sin(time + i * 0.5) * (100 + i * 8);
                    const py = centerY + Math.cos(time * 0.7 + i * 0.3) * (80 + i * 6);
                    ctx.beginPath();
                    ctx.arc(px, py, 2, 0, Math.PI * 2);
                    ctx.fillStyle = 'rgba(56, 189, 248, 0.5)';
                    ctx.fill();
                }}
            }}
            """
        ]
    
    def save_animation(self, project: AnimationProject, output_dir: str = None) -> Dict[str, str]:
        """保存动画项目和HTML文件"""
        save_dir = output_dir or self.output_dir
        os.makedirs(save_dir, exist_ok=True)
        
        # 保存项目JSON
        project_path = os.path.join(save_dir, f"{project.id}.json")
        with open(project_path, 'w', encoding='utf-8') as f:
            json.dump(project.to_dict(), f, ensure_ascii=False, indent=2)
        
        # 生成并保存HTML
        html_content = self.generate_html_animation(project)
        html_path = os.path.join(save_dir, f"{project.id}.html")
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return {
            "project_path": project_path,
            "html_path": html_path,
            "project_id": project.id
        }


# 单例实例
animation_engine = AnimationGenerationEngine()
