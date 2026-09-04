"""多模态语义关联分析器 - 处理文本、图像、视频等多模态内容的语义关联"""
import json
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class ModalityType(Enum):
    """模态类型"""
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    PPT = "ppt"
    LESSON_PLAN = "lesson_plan"


@dataclass
class MultimodalContent:
    """多模态内容项"""
    modality: ModalityType
    content: str  # 文本内容或描述
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    semantic_tags: List[str] = field(default_factory=list)


@dataclass
class SemanticRelation:
    """语义关联关系"""
    source_id: str
    target_id: str
    relation_type: str  # 关系类型：包含、引用、补充、对比等
    confidence: float
    description: str = ""


class MultimodalAnalyzer:
    """多模态语义关联分析器"""
    
    def __init__(self):
        # 语义关系类型定义
        self.relation_types = {
            "contains": "包含",
            "references": "引用",
            "supplements": "补充",
            "contrasts": "对比",
            "illustrates": "说明",
            "extends": "扩展",
            "examples": "举例"
        }
        
        # 关键词映射（用于语义标签提取）
        self.keyword_categories = {
            "概念定义": ["定义", "概念", "是什么", "含义", "概念是", "指的是"],
            "原理机制": ["原理", "机制", "工作原理", "如何工作", "机制是"],
            "应用场景": ["应用", "场景", "用途", "使用", "应用于", "用于"],
            "优缺点": ["优点", "缺点", "优势", "劣势", "好处", "坏处"],
            "步骤流程": ["步骤", "流程", "过程", "方法", "怎么做", "如何"],
            "案例示例": ["例子", "案例", "示例", "实例", "比如", "例如"],
            "对比分析": ["对比", "比较", "区别", "差异", "相同点", "不同点"],
            "历史发展": ["历史", "发展", "起源", "演变", "发展历程"]
        }
    
    def analyze_text_semantics(self, text: str) -> Dict[str, Any]:
        """分析文本语义
        
        返回语义标签和关键信息
        """
        result = {
            "semantic_tags": [],
            "key_points": [],
            "concepts": [],
            "summary": ""
        }
        
        # 提取语义标签
        for category, keywords in self.keyword_categories.items():
            for kw in keywords:
                if kw in text:
                    if category not in result["semantic_tags"]:
                        result["semantic_tags"].append(category)
                    break
        
        # 提取关键句子（包含关键词的句子）
        sentences = re.split(r'[。！？\n]', text)
        for sent in sentences:
            sent = sent.strip()
            if len(sent) > 10:  # 只保留有一定长度的句子
                # 检查是否包含重要信息
                if any(kw in sent for kws in self.keyword_categories.values() for kw in kws):
                    result["key_points"].append(sent)
        
        # 提取概念（引号或粗体标记的内容）
        concepts = re.findall(r'[【](.+?)[】]|\*\*(.+?)\*\*|__(.+?)__', text)
        for concept in concepts:
            for c in concept:
                if c and c.strip():
                    result["concepts"].append(c.strip())
        
        # 生成简要摘要
        if len(text) > 100:
            # 取前几句作为摘要
            result["summary"] = text[:200] + "..."
        
        return result
    
    def extract_key_concepts(self, text: str, max_concepts: int = 10) -> List[str]:
        """提取关键概念"""
        concepts = []
        
        # 1. 提取书名号、引号中的内容
        quoted = re.findall(r'[《](.+?)[》]|[【](.+?)[】]|[""](.+?)[""]', text)
        for match in quoted:
            for item in match:
                if item and item.strip() and len(item) > 1:
                    concepts.append(item.strip())
        
        # 2. 提取专业术语（大写开头的连续词）
        terms = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', text)
        for term in terms:
            if len(term) > 3:
                concepts.append(term)
        
        # 3. 去重并限制数量
        seen = set()
        unique_concepts = []
        for c in concepts:
            if c not in seen and len(c) > 1:
                seen.add(c)
                unique_concepts.append(c)
        
        return unique_concepts[:max_concepts]
    
    def find_semantic_relations(self, contents: List[MultimodalContent]) -> List[SemanticRelation]:
        """分析多个内容之间的语义关联"""
        relations = []
        
        # 两两比较所有内容对
        for i, source in enumerate(contents):
            for j, target in enumerate(contents):
                if i >= j:
                    continue
                
                # 基于关键词重叠分析关联
                source_keywords = set(source.semantic_tags + self.extract_key_concepts(source.content))
                target_keywords = set(target.semantic_tags + self.extract_key_concepts(target.content))
                
                # 计算关键词重叠度
                if source_keywords & target_keywords:
                    overlap = len(source_keywords & target_keywords)
                    total = len(source_keywords | target_keywords)
                    similarity = overlap / total if total > 0 else 0
                    
                    if similarity > 0.1:
                        # 确定关系类型
                        relation_type = self._determine_relation_type(source, target)
                        
                        relations.append(SemanticRelation(
                            source_id=str(i),
                            target_id=str(j),
                            relation_type=relation_type,
                            confidence=similarity,
                            description=f"{source.modality.value} 与 {target.modality.value} 存在语义关联"
                        ))
        
        return relations
    
    def _determine_relation_type(self, source: MultimodalContent, 
                                  target: MultimodalContent) -> str:
        """确定两个内容之间的关系类型"""
        source_text = source.content.lower()
        target_text = target.content.lower()
        
        # 基于内容分析关系类型
        if any(kw in source_text for kw in ["例如", "比如", "例子"]):
            return "examples"
        if any(kw in source_text for kw in ["说明", "解释", "展示"]):
            return "illustrates"
        if any(kw in source_text for kw in ["补充", "另外", "还有"]):
            return "supplements"
        if any(kw in source_text for kw in ["对比", "相比", "不同"]):
            return "contrasts"
        if len(source_text) > len(target_text) * 2:
            return "contains"
        
        return "references"
    
    def generate_cross_modal_description(self, content: MultimodalContent, 
                                         target_modality: ModalityType) -> str:
        """生成跨模态描述
        
        为给定内容生成适合目标模态的描述
        """
        if target_modality == ModalityType.IMAGE:
            return self._generate_image_description(content)
        elif target_modality == ModalityType.VIDEO:
            return self._generate_video_script(content)
        elif target_modality == ModalityType.PPT:
            return self._generate_ppt_outline(content)
        elif target_modality == ModalityType.LESSON_PLAN:
            return self._generate_lesson_plan_hint(content)
        else:
            return content.content
    
    def _generate_image_description(self, content: MultimodalContent) -> str:
        """生成图像描述"""
        concepts = self.extract_key_concepts(content.content)
        tags = content.semantic_tags
        
        desc_parts = []
        if concepts:
            desc_parts.append(f"图像主题：{', '.join(concepts[:3])}")
        if tags:
            desc_parts.append(f"内容类型：{', '.join(tags)}")
        
        return "；".join(desc_parts) if desc_parts else "教学示意图"
    
    def _generate_video_script(self, content: MultimodalContent) -> str:
        """生成视频脚本建议"""
        concepts = self.extract_key_concepts(content.content)
        
        script = f"""视频主题：{concepts[0] if concepts else "教学内容"}

脚本结构：
1. 开场介绍（30秒）：介绍主题背景
2. 核心概念讲解（2分钟）：详细解释关键概念
3. 示例演示（1.5分钟）：通过例子说明原理
4. 总结回顾（30秒）：重点回顾
"""
        return script
    
    def _generate_ppt_outline(self, content: MultimodalContent) -> str:
        """生成PPT大纲"""
        concepts = self.extract_key_concepts(content.content)
        tags = content.semantic_tags
        
        outline = f"""PPT主题：{concepts[0] if concepts else "教学内容"}

幻灯片大纲：
1. 封面页
2. 目录页
"""
        for i, tag in enumerate(tags[:5], 3):
            outline += f"{i}. {tag}讲解页\n"
        
        outline += "6. 总结页\n7. Q&A页"
        return outline
    
    def _generate_lesson_plan_hint(self, content: MultimodalContent) -> str:
        """生成教案提示"""
        concepts = self.extract_key_concepts(content.content)
        
        hint = f"""教案核心知识点：{', '.join(concepts[:5])}

教学建议：
- 教学重点：核心概念讲解
- 教学难点：原理机制理解
- 教学方法：案例教学、互动讨论
"""
        return hint
    
    def create_knowledge_graph(self, contents: List[MultimodalContent]) -> Dict[str, Any]:
        """创建知识图谱"""
        nodes = []
        edges = []
        
        # 创建节点
        for i, content in enumerate(contents):
            node = {
                "id": str(i),
                "type": content.modality.value,
                "label": content.content[:50] + "..." if len(content.content) > 50 else content.content,
                "concepts": self.extract_key_concepts(content.content),
                "tags": content.semantic_tags
            }
            nodes.append(node)
        
        # 创建边（语义关联）
        relations = self.find_semantic_relations(contents)
        for rel in relations:
            edge = {
                "source": rel.source_id,
                "target": rel.target_id,
                "relation": rel.relation_type,
                "confidence": rel.confidence,
                "label": self.relation_types.get(rel.relation_type, rel.relation_type)
            }
            edges.append(edge)
        
        return {
            "nodes": nodes,
            "edges": edges,
            "summary": f"共 {len(nodes)} 个内容节点，{len(edges)} 条语义关联"
        }


# 全局实例
multimodal_analyzer = MultimodalAnalyzer()
