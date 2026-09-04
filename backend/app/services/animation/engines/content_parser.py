"""
内容解析引擎
功能：语义分析、知识点提取、学科识别、动画类型匹配
输入：教学文本内容
输出：结构化知识点列表 + 内容分析结果
"""
import re
import uuid
from typing import List, Dict, Optional, Tuple
from dataclasses import asdict

from ..schemas.animation_schema import (
    SubjectType,
    ContentAnalysisResult,
    KnowledgePoint,
    SUBJECT_KEYWORDS,
    ComponentType
)


class ContentParser:
    """内容解析引擎 - 将教学文本转换为结构化数据"""
    
    def __init__(self):
        self.subject_keywords = SUBJECT_KEYWORDS
        
        # 知识点提取模式
        self.concept_patterns = [
            r'([\u4e00-\u9fffA-Za-z]{2,15})是指',
            r'([\u4e00-\u9fffA-Za-z]{2,15})的定义',
            r'所谓([\u4e00-\u9fffA-Za-z]{2,15})',
            r'([\u4e00-\u9fffA-Za-z]{2,15})：',
            r'【([\u4e00-\u9fffA-Za-z]{2,15})】',
        ]
        
        # 步骤提取模式
        self.step_patterns = [
            r'第[一二三四五六七八九十\d]+步[：:]',
            r'^[\d一二三四五六七八九十]+[\.、．)）]\s*',
            r'^[\(（][\d一二三四五六七八九十]+[\)）]\s*',
            r'步骤[一二三四五六七八九十\d]+[：:]',
        ]
        
        # 难度等级词汇
        self.difficulty_words = {
            1: ['基础', '入门', '简单', '初级', '概念'],
            2: ['进阶', '中级', '理解', '应用'],
            3: ['高级', '复杂', '深入', '综合', '难点', '重点'],
        }
        
        # 受众识别
        self.audience_keywords = {
            '小学生': ['小学', '儿童', '小朋友'],
            '初中生': ['初中', '初一', '初二', '初三'],
            '高中生': ['高中', '高一', '高二', '高三', '高考'],
            '大学生': ['大学', '本科', '考研', '专业'],
            '研究生': ['研究生', '硕士', '博士', '学术'],
        }

    def parse(self, content: str, topic: str = "", audience: str = "") -> ContentAnalysisResult:
        """解析教学内容"""
        content = self._clean_content(content)
        full_content = f"{topic} {content}".strip()
        
        # 1. 识别学科
        subject = self._identify_subject(full_content)
        
        # 2. 提取知识点
        knowledge_points = self._extract_knowledge_points(full_content, subject)
        
        # 3. 提取关键概念
        key_concepts = self._extract_key_concepts(full_content)
        
        # 4. 识别难度
        difficulty = self._identify_difficulty(full_content)
        
        # 5. 识别受众
        target_audience = audience or self._identify_audience(full_content)
        
        # 6. 建议场景
        suggested_scenes = self._suggest_scenes(content, topic, knowledge_points, subject)
        
        # 7. 推荐组件类型
        recommended_components = self._recommend_components(subject, key_concepts)
        
        return ContentAnalysisResult(
            subject=subject,
            knowledge_points=knowledge_points,
            suggested_scenes=suggested_scenes,
            recommended_components=recommended_components,
            key_concepts=key_concepts,
            difficulty_level=difficulty,
            target_audience=target_audience
        )

    def _clean_content(self, content: str) -> str:
        """清理内容"""
        if not content:
            return ""
        content = re.sub(r'\s+', ' ', content)
        content = re.sub(r'\n+', '\n', content)
        return content.strip()

    def _identify_subject(self, content: str) -> SubjectType:
        """识别学科类型"""
        scores = {}
        
        for subject, keywords in self.subject_keywords.items():
            score = 0
            content_lower = content.lower()
            for kw in keywords:
                if kw in content_lower:
                    score += 1
            scores[subject] = score
        
        max_score = max(scores.values()) if scores else 0
        if max_score > 0:
            for subject, score in scores.items():
                if score == max_score:
                    return subject
        
        return SubjectType.GENERAL

    def _extract_knowledge_points(self, content: str, subject: SubjectType) -> List[KnowledgePoint]:
        """提取知识点"""
        points = []
        seen_concepts = set()
        
        # 1. 使用模式匹配提取概念
        for pattern in self.concept_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                concept = match.strip()
                if len(concept) >= 2 and concept not in seen_concepts:
                    seen_concepts.add(concept)
                    point = self._create_knowledge_point(concept, content, subject)
                    points.append(point)
        
        # 2. 提取步骤作为知识点
        steps = self._extract_steps(content)
        for i, step in enumerate(steps[:6]):
            concept = step[:20] if len(step) > 20 else step
            if concept not in seen_concepts:
                seen_concepts.add(concept)
                point = KnowledgePoint(
                    id=f"kp_step_{uuid.uuid4().hex[:6]}",
                    name=f"步骤{i+1}",
                    description=step,
                    subject=subject,
                    difficulty=1,
                    visual_hints=["流程展示"]
                )
                points.append(point)
        
        # 3. 如果没有提取到，创建默认知识点
        if not points:
            default_point = KnowledgePoint(
                id=f"kp_default_{uuid.uuid4().hex[:6]}",
                name="核心概念",
                description=content[:200] if len(content) > 200 else content,
                subject=subject,
                difficulty=1,
                visual_hints=["概念展示"]
            )
            points.append(default_point)
        
        return points[:8]  # 最多8个知识点

    def _create_knowledge_point(self, concept: str, content: str, subject: SubjectType) -> KnowledgePoint:
        """创建知识点对象"""
        # 提取概念相关的上下文
        description = self._extract_concept_description(concept, content)
        
        # 确定难度
        difficulty = self._identify_difficulty(description)
        
        # 可视化提示
        visual_hints = self._suggest_visual_hints(concept, subject)
        
        return KnowledgePoint(
            id=f"kp_{uuid.uuid4().hex[:8]}",
            name=concept,
            description=description,
            subject=subject,
            difficulty=difficulty,
            visual_hints=visual_hints
        )

    def _extract_concept_description(self, concept: str, content: str) -> str:
        """提取概念的描述"""
        # 查找概念附近的句子
        sentences = re.split(r'[。！？.!?]', content)
        for sentence in sentences:
            if concept in sentence:
                return sentence.strip()[:150]
        return f"{concept}的相关概念"

    def _extract_steps(self, content: str) -> List[str]:
        """提取步骤"""
        steps = []
        lines = content.split('\n')
        
        current_step = ""
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 检查是否是新步骤
            is_new_step = False
            for pattern in self.step_patterns:
                if re.match(pattern, line):
                    is_new_step = True
                    break
            
            if is_new_step:
                if current_step:
                    steps.append(current_step.strip())
                # 移除步骤标记
                for pattern in self.step_patterns:
                    line = re.sub(pattern, '', line)
                current_step = line
            elif current_step:
                current_step += " " + line
        
        if current_step:
            steps.append(current_step.strip())
        
        return steps

    def _extract_key_concepts(self, content: str) -> List[str]:
        """提取关键概念"""
        concepts = set()
        
        # 提取中文名词短语（2-6个汉字）
        cn_phrases = re.findall(r'[\u4e00-\u9fff]{2,6}', content)
        for phrase in cn_phrases:
            if len(phrase) >= 2:
                concepts.add(phrase)
        
        # 提取英文术语
        en_terms = re.findall(r'[A-Za-z]{3,}', content)
        for term in en_terms:
            concepts.add(term)
        
        return list(concepts)[:10]

    def _identify_difficulty(self, content: str) -> int:
        """识别难度等级"""
        content_lower = content.lower()
        scores = {1: 0, 2: 0, 3: 0}
        
        for level, words in self.difficulty_words.items():
            for word in words:
                if word in content_lower:
                    scores[level] += 1
        
        max_score = max(scores.values())
        if max_score > 0:
            for level, score in scores.items():
                if score == max_score:
                    return level
        
        return 1

    def _identify_audience(self, content: str) -> str:
        """识别目标受众"""
        content_lower = content.lower()
        
        for audience, keywords in self.audience_keywords.items():
            for kw in keywords:
                if kw in content_lower:
                    return audience
        
        return "大学生"  # 默认

    def _suggest_scenes(self, content: str, topic: str, 
                       knowledge_points: List[KnowledgePoint], 
                       subject: SubjectType) -> List[Dict]:
        """建议场景编排"""
        scenes = []
        scene_templates = self._get_scene_templates(subject)
        
        # 场景1：引入概念
        scenes.append({
            "id": f"scene_intro_{uuid.uuid4().hex[:6]}",
            "title": f"引入：{topic}",
            "description": f"介绍{topic}的背景和重要性",
            "duration": 8.0,
            "narration": f"今天我们来学习{topic}",
            "components": ["title", "background"],
            "key_points": ["背景介绍", "学习目标"]
        })
        
        # 中间场景：每个知识点一个场景
        for i, kp in enumerate(knowledge_points[:4]):
            template = scene_templates[i % len(scene_templates)]
            scenes.append({
                "id": f"scene_kp_{uuid.uuid4().hex[:6]}",
                "title": kp.name,
                "description": kp.description,
                "duration": 10.0,
                "narration": f"接下来讲解{kp.name}",
                "components": template["components"],
                "key_points": [kp.name] + kp.related_concepts[:2],
                "knowledge_point_id": kp.id
            })
        
        # 最后场景：总结
        scenes.append({
            "id": f"scene_summary_{uuid.uuid4().hex[:6]}",
            "title": "总结回顾",
            "description": f"回顾{topic}的核心要点",
            "duration": 6.0,
            "narration": "今天的学习内容就到这里，总结一下要点",
            "components": ["summary", "key_points"],
            "key_points": [kp.name for kp in knowledge_points[:4]]
        })
        
        return scenes

    def _get_scene_templates(self, subject: SubjectType) -> List[Dict]:
        """获取场景模板"""
        templates = {
            SubjectType.MATHEMATICS: [
                {"components": ["coordinate_system", "function_graph", "text_explanation"]},
                {"components": ["geometric_shape", "animation", "text_explanation"]},
                {"components": ["formula", "step_by_step", "text_explanation"]},
                {"components": ["example", "graph", "text_explanation"]},
            ],
            SubjectType.PHYSICS: [
                {"components": ["motion_trajectory", "force_diagram", "text_explanation"]},
                {"components": ["experiment", "data_plot", "text_explanation"]},
                {"components": ["formula", "animation", "text_explanation"]},
                {"components": ["real_world", "diagram", "text_explanation"]},
            ],
            SubjectType.CHEMISTRY: [
                {"components": ["molecule_structure", "text_explanation"]},
                {"components": ["reaction_process", "animation", "text_explanation"]},
                {"components": ["periodic_table", "element", "text_explanation"]},
                {"components": ["experiment", "equation", "text_explanation"]},
            ],
            SubjectType.BIOLOGY: [
                {"components": ["cell_structure", "labels", "text_explanation"]},
                {"components": ["physiological_process", "animation", "text_explanation"]},
                {"components": ["dna_model", "text_explanation"]},
                {"components": ["organism", "diagram", "text_explanation"]},
            ],
        }
        
        return templates.get(subject, [
            {"components": ["concept", "visualization", "text_explanation"]},
            {"components": ["example", "animation", "text_explanation"]},
            {"components": ["diagram", "labels", "text_explanation"]},
            {"components": ["summary", "key_points", "text_explanation"]},
        ])

    def _recommend_components(self, subject: SubjectType, 
                             key_concepts: List[str]) -> List[ComponentType]:
        """推荐组件类型"""
        component_map = {
            SubjectType.MATHEMATICS: [
                ComponentType.COORDINATE_SYSTEM,
                ComponentType.FUNCTION_GRAPH,
                ComponentType.GEOMETRIC_SHAPE,
                ComponentType.TEXT,
            ],
            SubjectType.PHYSICS: [
                ComponentType.MOTION_TRAJECTORY,
                ComponentType.FORCE_DIAGRAM,
                ComponentType.TEXT,
                ComponentType.ARROW,
            ],
            SubjectType.CHEMISTRY: [
                ComponentType.MOLECULE_STRUCTURE,
                ComponentType.REACTION_PROCESS,
                ComponentType.TEXT,
                ComponentType.CIRCLE,
            ],
            SubjectType.BIOLOGY: [
                ComponentType.CELL_STRUCTURE,
                ComponentType.PHYSIOLOGICAL_PROCESS,
                ComponentType.DNA_MODEL,
                ComponentType.TEXT,
            ],
            SubjectType.GEOGRAPHY: [
                ComponentType.FLOW_CHART,
                ComponentType.TIMELINE,
                ComponentType.TEXT,
                ComponentType.IMAGE,
            ],
            SubjectType.HISTORY: [
                ComponentType.TIMELINE,
                ComponentType.FLOW_CHART,
                ComponentType.TEXT,
                ComponentType.IMAGE,
            ],
        }
        
        return component_map.get(subject, [
            ComponentType.CIRCLE,
            ComponentType.RECTANGLE,
            ComponentType.TEXT,
            ComponentType.ARROW,
        ])

    def _suggest_visual_hints(self, concept: str, subject: SubjectType) -> List[str]:
        """建议可视化方式"""
        hints_map = {
            SubjectType.MATHEMATICS: ["函数图像", "几何图形", "坐标系", "公式推导"],
            SubjectType.PHYSICS: ["运动轨迹", "受力分析", "实验演示", "数据图表"],
            SubjectType.CHEMISTRY: ["分子结构", "反应过程", "化学键", "元素周期"],
            SubjectType.BIOLOGY: ["细胞结构", "生理过程", "DNA模型", "组织结构"],
            SubjectType.GEOGRAPHY: ["地图", "剖面图", "流程图", "时间线"],
            SubjectType.HISTORY: ["时间线", "地图", "人物关系", "事件流程"],
        }
        
        return hints_map.get(subject, ["概念展示", "流程图解", "要点列表"])


# 单例实例
content_parser = ContentParser()
