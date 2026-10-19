# -*- coding: utf-8 -*-
"""
课件生成服务V2 - 支持SSE实时进度推送的升级版
严格遵循Office兼容性标准，解决中文乱码问题

核心改进：
1. 字体标准化：中文使用"微软雅黑"，西文使用"Arial"
2. 尺寸规范：16:9比例 (13.333 x 7.5 英寸)
3. 内容规范：单页单核心知识点，每页≤20字标题，≤5条要点
4. SSE推送：分6阶段推送进度和预览数据
5. 自动校验：生成后自动校验文件完整性

Author: Matrix Agent
"""

import os
import json
import uuid
import asyncio
import traceback
from typing import Optional, Dict, List, Any
from datetime import datetime
from pathlib import Path

# 导入SSE管理器
from .sse_progress_manager import (
    sse_manager, 
    GenerationStage, 
    TaskStatus
)

# 导入LLM服务
from .llm_service import llm_service


class CoursewareGeneratorV2:
    """
    课件生成器V2 - 支持SSE实时进度推送
    
    使用示例:
    ```python
    generator = CoursewareGeneratorV2()
    task_id = generator.create_task(
        topic="Python基础",
        audience="大一新生",
        duration=45
    )
    
    # 启动异步生成任务
    asyncio.create_task(generator.generate_with_progress(task_id))
    
    # 前端通过 SSE /api/courseware/sse/{task_id} 获取进度
    ```
    """
    
    def __init__(self, output_dir: str = "generated_courseware"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # 主题色配置 - 使用RGB元组确保兼容性
        self.theme_colors = {
            "蓝色系": {
                "primary": (52, 152, 219),      # 主色
                "secondary": (41, 128, 185),   # 辅助色
                "accent": (46, 204, 113),      # 强调色
                "text": (44, 62, 80),          # 文本色
                "light": (189, 195, 199)       # 浅色
            },
            "绿色系": {
                "primary": (46, 204, 113),
                "secondary": (39, 174, 96),
                "accent": (52, 152, 219),
                "text": (39, 174, 96),
                "light": (203, 219, 201)
            },
            "红色系": {
                "primary": (231, 76, 60),
                "secondary": (192, 57, 43),
                "accent": (241, 196, 15),
                "text": (155, 89, 182),
                "light": (235, 205, 206)
            },
            "紫色系": {
                "primary": (155, 89, 182),
                "secondary": (142, 68, 173),
                "accent": (241, 196, 15),
                "text": (123, 31, 162),
                "light": (215, 190, 223)
            },
            "橙色系": {
                "primary": (243, 156, 18),
                "secondary": (230, 126, 34),
                "accent": (52, 152, 219),
                "text": (211, 84, 0),
                "light": (249, 231, 207)
            }
        }
        
        # 字体配置 - 兼容性优先
        self.fonts = {
            "chinese": "微软雅黑",      # 中文优先
            "english": "Arial",          # 西文
            "code": "Consolas"           # 代码
        }
        
        # 字号配置 (磅)
        self.font_sizes = {
            "title": 36,      # 页面标题
            "subtitle": 28,   # 副标题
            "heading": 24,    # 小标题
            "body": 18,       # 正文
            "small": 14       # 小字
        }
    
    def create_task(
        self,
        topic: str,
        audience: str = "大学生",
        duration: int = 45,
        subject: str = "通用",
        theme_color: str = "蓝色系",
        key_points: List[str] = None,
        reference_docs: List[str] = None,
        provider: str = None
    ) -> str:
        """
        创建生成任务
        
        Args:
            topic: 课程主题
            audience: 目标受众
            duration: 课时时长(分钟)
            subject: 学科类型
            theme_color: 主题色
            key_points: 核心知识点
            reference_docs: 参考文档
            provider: LLM提供商
        
        Returns:
            task_id: 任务ID
        """
        params = {
            "topic": topic,
            "audience": audience,
            "duration": duration,
            "subject": subject,
            "theme_color": theme_color,
            "key_points": key_points or [],
            "reference_docs": reference_docs or [],
            "provider": provider
        }
        
        task_id = sse_manager.create_task_sync("ppt", params)
        return task_id
    
    async def generate_with_progress(self, task_id: str) -> Dict:
        """
        带进度推送的生成任务
        
        Args:
            task_id: 任务ID
        
        Returns:
            生成结果
        """
        task = sse_manager.get_task_sync(task_id)
        if not task:
            return {"error": "任务不存在"}
        
        try:
            params = task.params
            
            # ========== 阶段1: 初始化 ==========
            await sse_manager.update_progress(
                task_id,
                GenerationStage.INIT,
                2,
                "正在初始化生成环境...",
                {"init_time": datetime.now().isoformat()}
            )
            
            # 设置LLM提供商
            if params.get("provider"):
                llm_service.set_provider(params["provider"])
            
            # 创建输出目录
            task_dir = await self._prepare_output_dir(params["topic"])
            
            await sse_manager.update_progress(
                task_id,
                GenerationStage.INIT,
                5,
                "环境初始化完成",
                {"task_dir": task_dir}
            )
            
            # ========== 阶段2: 需求解析 ==========
            await sse_manager.update_progress(
                task_id,
                GenerationStage.REQUIREMENTS_PARSING,
                5,
                "正在解析用户需求...",
                {"current_action": "analyzing_requirements"}
            )
            
            requirements = await self._analyze_requirements(
                topic=params["topic"],
                audience=params["audience"],
                duration=params["duration"],
                subject=params["subject"],
                key_points=params.get("key_points", [])
            )
            
            await sse_manager.update_progress(
                task_id,
                GenerationStage.REQUIREMENTS_PARSING,
                15,
                f"需求解析完成: 识别到{len(requirements.get('teaching_goals', {}).get('knowledge_goals', []))}个知识目标",
                {"requirements": requirements}
            )
            
            # ========== 阶段3: 大纲生成 ==========
            await sse_manager.update_progress(
                task_id,
                GenerationStage.OUTLINE_GENERATION,
                15,
                "正在生成课程大纲...",
                {"current_action": "generating_outline"}
            )
            
            outline = await self._generate_outline(requirements)
            
            await sse_manager.update_progress(
                task_id,
                GenerationStage.OUTLINE_GENERATION,
                30,
                f"大纲生成完成: 共{len(outline)}页",
                {"outline": outline}
            )
            
            # ========== 阶段4: 内容生成 ==========
            await sse_manager.update_progress(
                task_id,
                GenerationStage.CONTENT_GENERATION,
                30,
                "正在生成详细内容...",
                {"current_action": "generating_content"}
            )
            
            # 分页生成内容，每生成一页推送一次预览
            detailed_pages = []
            total_pages = len(outline)
            
            for i, page_outline in enumerate(outline):
                page_num = i + 1
                progress = 30 + (i / total_pages) * 40  # 30-70%
                
                await sse_manager.update_progress(
                    task_id,
                    GenerationStage.CONTENT_GENERATION,
                    progress,
                    f"正在生成第{page_num}页/共{total_pages}页...",
                    {
                        "current_page": page_num,
                        "total_pages": total_pages,
                        "page_type": page_outline.get("page_type", "")
                    }
                )
                
                # 生成单页内容
                page_content = await self._generate_page_content(
                    page_outline, 
                    requirements,
                    i
                )
                detailed_pages.append(page_content)
                
                # 发送预览更新
                await sse_manager.send_preview(
                    task_id,
                    page_num,
                    self._convert_to_preview(page_content, params.get("theme_color", "蓝色系"))
                )
            
            await sse_manager.update_progress(
                task_id,
                GenerationStage.CONTENT_GENERATION,
                70,
                "内容生成完成",
                {"total_pages": len(detailed_pages)}
            )
            
            # ========== 阶段5: 样式渲染 ==========
            await sse_manager.update_progress(
                task_id,
                GenerationStage.STYLE_RENDERING,
                70,
                "正在应用视觉样式...",
                {"current_action": "applying_style"}
            )
            
            style = self._get_visual_style(params.get("theme_color", "蓝色系"))
            
            await sse_manager.update_progress(
                task_id,
                GenerationStage.STYLE_RENDERING,
                80,
                "样式应用完成",
                {"style": style}
            )
            
            # ========== 阶段6: 文件生成 ==========
            await sse_manager.update_progress(
                task_id,
                GenerationStage.FILE_GENERATION,
                80,
                "正在生成PPTX文件...",
                {"current_action": "generating_pptx"}
            )
            
            # 生成PPTX文件
            pptx_path = await self._create_pptx_file(
                topic=params["topic"],
                pages=detailed_pages,
                style=style,
                theme_color=params.get("theme_color", "蓝色系"),
                task_dir=task_dir
            )
            
            await sse_manager.update_progress(
                task_id,
                GenerationStage.FILE_GENERATION,
                90,
                "PPTX文件生成完成",
                {"pptx_path": pptx_path}
            )
            
            # ========== 阶段7: 校验 ==========
            await sse_manager.update_progress(
                task_id,
                GenerationStage.VALIDATION,
                90,
                "正在校验文件完整性...",
                {"current_action": "validating"}
            )
            
            # 文件校验
            validation_result = await self._validate_pptx(pptx_path)
            
            if not validation_result["valid"]:
                await sse_manager.update_progress(
                    task_id,
                    GenerationStage.VALIDATION,
                    90,
                    f"校验发现问题: {validation_result.get('error', '未知错误')}，正在重试...",
                    {"validation_error": validation_result.get("error")}
                )
                
                # 重新生成
                pptx_path = await self._create_pptx_file(
                    topic=params["topic"],
                    pages=detailed_pages,
                    style=style,
                    theme_color=params.get("theme_color", "蓝色系"),
                    task_dir=task_dir
                )
                
                validation_result = await self._validate_pptx(pptx_path)
            
            await sse_manager.update_progress(
                task_id,
                GenerationStage.VALIDATION,
                95,
                "文件校验通过 ✓" if validation_result["valid"] else "文件校验失败",
                {"validation": validation_result}
            )
            
            # ========== 完成 ==========
            result = {
                "task_id": task_id,
                "topic": params["topic"],
                "duration": params["duration"],
                "audience": params["audience"],
                "pages_count": len(detailed_pages),
                "pptx_path": pptx_path,
                "task_dir": task_dir,
                "validation": validation_result,
                "generated_at": datetime.now().isoformat()
            }
            
            await sse_manager.complete_task(task_id, result)
            
            return result
            
        except asyncio.CancelledError:
            await sse_manager.send_error(task_id, "任务被用户取消")
            raise
            
        except Exception as e:
            error_msg = f"生成失败: {str(e)}"
            await sse_manager.send_error(task_id, error_msg, traceback.format_exc())
            return {"error": error_msg, "traceback": traceback.format_exc()}
    
    async def _prepare_output_dir(self, topic: str) -> str:
        """准备输出目录"""
        task_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_topic = self._safe_filename(topic)
        task_dir = os.path.join(self.output_dir, f"{safe_topic}_{timestamp}_{task_id}")
        os.makedirs(task_dir, exist_ok=True)
        return task_dir
    
    def _safe_filename(self, filename: str) -> str:
        """生成安全文件名"""
        illegal_chars = '<>:"/\\|?*'
        for char in illegal_chars:
            filename = filename.replace(char, '_')
        return filename[:50]  # 限制长度
    
    async def _analyze_requirements(
        self,
        topic: str,
        audience: str,
        duration: int,
        subject: str,
        key_points: List[str]
    ) -> Dict:
        """分析需求"""
        
        # 根据时长确定页数
        if duration <= 30:
            page_count = 8
        elif duration <= 45:
            page_count = 12
        else:
            page_count = 16
        
        # 调用LLM生成教学目标
        goals_prompt = f"""请为主题"{topic}"、面向{audience}的课程定义3-5个可落地的核心教学目标。

要求：
1. 知识目标：学生应该掌握的概念、原理
2. 能力目标：学生应该具备的分析/应用/实践能力
3. 情感目标：学生应该形成的科学态度或价值观

请以JSON格式输出：
{{
    "knowledge_goals": ["目标1", "目标2"],
    "ability_goals": ["能力1", "能力2"],
    "emotional_goals": ["态度1"]
}}
"""
        
        goals_response = llm_service.chat(goals_prompt, purpose="courseware_content")
        
        try:
            teaching_goals = json.loads(goals_response)
        except:
            teaching_goals = {
                "knowledge_goals": [f"理解{topic}的基本概念"],
                "ability_goals": [f"能够应用{topic}的核心知识解决问题"],
                "emotional_goals": [f"培养对{topic}的学习兴趣"]
            }
        
        return {
            "topic": topic,
            "audience": audience,
            "duration": duration,
            "subject": subject,
            "page_count": page_count,
            "key_points": key_points,
            "teaching_goals": teaching_goals
        }
    
    async def _generate_outline(self, requirements: Dict) -> List[Dict]:
        """生成PPT大纲"""
        
        topic = requirements["topic"]
        audience = requirements["audience"]
        page_count = requirements["page_count"]
        teaching_goals = requirements.get("teaching_goals", {})
        
        outline_prompt = f"""请为主题"{topic}"生成一个{page_count}页左右的PPT大纲。

面向对象: {audience}
课程时长: {requirements["duration"]}分钟

教学目标：
- 知识目标: {", ".join(teaching_goals.get("knowledge_goals", []))}
- 能力目标: {", ".join(teaching_goals.get("ability_goals", []))}

要求：
1. 必须包含：封面页、目录页、至少3个知识点页、习题页、总结页
2. 每页标题≤20字
3. 每页要点≤5条，单条≤30字
4. 遵循"单页单核心"原则

请以JSON格式输出页面数组：
[
    {{"page_num": 1, "page_type": "cover", "core_topic": "封面标题", "content_outline": ["要点1", "要点2"]}},
    {{"page_num": 2, "page_type": "toc", "core_topic": "目录", "content_outline": ["模块1", "模块2", ...]}},
    ...
]
"""
        
        outline_response = llm_service.chat(outline_prompt, purpose="courseware_content")
        
        try:
            outline = json.loads(outline_response)
            # 确保有必备页面
            page_types = [p.get("page_type") for p in outline]
            if "cover" not in page_types:
                outline.insert(0, {"page_num": 1, "page_type": "cover", "core_topic": topic, "content_outline": [topic]})
            # 重新编号
            for i, page in enumerate(outline):
                page["page_num"] = i + 1
            return outline
        except:
            # 生成默认大纲
            return self._generate_default_outline(requirements)
    
    def _generate_default_outline(self, requirements: Dict) -> List[Dict]:
        """生成默认大纲"""
        topic = requirements["topic"]
        page_count = requirements.get("page_count", 10)
        
        outline = [
            {"page_num": 1, "page_type": "cover", "core_topic": topic, "content_outline": [topic]},
            {"page_num": 2, "page_type": "toc", "core_topic": "课程目录", "content_outline": ["导入", "知识点1", "知识点2", "知识点3", "总结"]},
            {"page_num": 3, "page_type": "knowledge", "core_topic": f"{topic} - 导入", "content_outline": ["引入案例", "问题驱动", "学习目标"]},
            {"page_num": 4, "page_type": "knowledge", "core_topic": f"{topic} - 核心概念", "content_outline": ["基本定义", "重要特征", "关键要素"]},
            {"page_num": 5, "page_type": "knowledge", "core_topic": f"{topic} - 原理机制", "content_outline": ["工作原理", "实现机制", "关键步骤"]},
            {"page_num": 6, "page_type": "knowledge", "core_topic": f"{topic} - 应用实践", "content_outline": ["应用场景", "案例分析", "实践要点"]},
            {"page_num": 7, "page_type": "exercise", "core_topic": "课堂练习", "content_outline": ["思考题", "实践题", "讨论题"]},
            {"page_num": 8, "page_type": "summary", "core_topic": "课程总结", "content_outline": ["核心回顾", "目标达成", "课后作业"]}
        ]
        
        # 如果需要更多页面，添加更多知识点页
        while len(outline) < page_count:
            idx = len(outline)
            outline.insert(-2, {
                "page_num": idx + 1,
                "page_type": "knowledge",
                "core_topic": f"{topic} - 深入理解",
                "content_outline": ["深度分析", "拓展应用", "注意事项"]
            })
            for i, page in enumerate(outline):
                page["page_num"] = i + 1
        
        return outline[:page_count]
    
    async def _generate_page_content(self, page_outline: Dict, requirements: Dict, index: int) -> Dict:
        """生成单页详细内容"""
        
        page_type = page_outline.get("page_type", "knowledge")
        core_topic = page_outline.get("core_topic", "")
        topic = requirements["topic"]
        audience = requirements["audience"]
        
        if page_type == "cover":
            return {
                "page_num": index + 1,
                "page_type": "cover",
                "core_topic": core_topic,
                "main_title": topic,
                "subtitle": f"面向{audience}的专业课程",
                "instructor_info": "授课教师",
                "date": datetime.now().strftime("%Y年%m月%d日")
            }
        
        elif page_type == "toc":
            outline_pages = requirements.get("outline", [])
            toc_items = [p.get("core_topic", "") for p in outline_pages if p.get("page_type") != "cover"]
            return {
                "page_num": index + 1,
                "page_type": "toc",
                "core_topic": core_topic,
                "toc_items": toc_items
            }
        
        elif page_type == "knowledge":
            content_prompt = f"""请为"{core_topic}"页面生成详细内容。

课程主题: {topic}
面向对象: {audience}

要求：
1. 3-5个核心要点，每条≤30字
2. 1个配套案例
3. 1条讲解要点

请以JSON格式输出：
{{
    "page_num": {index + 1},
    "page_type": "knowledge",
    "core_topic": "{core_topic}",
    "key_points": ["要点1", "要点2", "要点3"],
    "case_study": "案例描述",
    "teaching_notes": "讲解要点"
}}
"""
            content_response = llm_service.chat(content_prompt, purpose="courseware_content")
            
            try:
                content = json.loads(content_response)
                content["page_num"] = index + 1
                return content
            except:
                return {
                    "page_num": index + 1,
                    "page_type": "knowledge",
                    "core_topic": core_topic,
                    "key_points": ["核心概念讲解", "重点分析", "应用实践"],
                    "case_study": "典型案例分析",
                    "teaching_notes": "重点强调核心内容"
                }
        
        elif page_type == "exercise":
            return {
                "page_num": index + 1,
                "page_type": "exercise",
                "core_topic": core_topic,
                "exercises": [
                    {
                        "question": f"关于{topic}的核心问题？",
                        "options": ["A. 选项1", "B. 选项2", "C. 选项3", "D. 选项4"],
                        "answer": "A"
                    }
                ],
                "interaction_suggestions": "组织小组讨论"
            }
        
        elif page_type == "summary":
            return {
                "page_num": index + 1,
                "page_type": "summary",
                "core_topic": core_topic,
                "knowledge_review": [f"回顾{topic}的核心知识点"],
                "homework": f"完成与{topic}相关的练习题"
            }
        
        else:
            return {
                "page_num": index + 1,
                "page_type": page_type,
                "core_topic": core_topic,
                "key_points": ["内容要点"]
            }
    
    def _convert_to_preview(self, page_content: Dict, theme_color: str) -> Dict:
        """转换为预览数据格式"""
        
        colors = self.theme_colors.get(theme_color, self.theme_colors["蓝色系"])
        
        preview = {
            "page_num": page_content.get("page_num", 1),
            "page_type": page_content.get("page_type", ""),
            "core_topic": page_content.get("core_topic", ""),
            "theme": {
                "primary_color": f"rgb({colors['primary'][0]}, {colors['primary'][1]}, {colors['primary'][2]})",
                "secondary_color": f"rgb({colors['secondary'][0]}, {colors['secondary'][1]}, {colors['secondary'][2]})",
                "text_color": f"rgb({colors['text'][0]}, {colors['text'][1]}, {colors['text'][2]})"
            }
        }
        
        # 根据页面类型添加预览内容
        if page_content.get("page_type") == "cover":
            preview["main_title"] = page_content.get("main_title", "")
            preview["subtitle"] = page_content.get("subtitle", "")
            preview["instructor_info"] = page_content.get("instructor_info", "")
            preview["date"] = page_content.get("date", "")
        
        elif page_content.get("page_type") == "toc":
            preview["toc_items"] = page_content.get("toc_items", [])
        
        else:
            preview["key_points"] = page_content.get("key_points", [])
            preview["case_study"] = page_content.get("case_study", "")
        
        return preview
    
    def _get_visual_style(self, theme_color: str) -> Dict:
        """获取视觉样式配置"""
        
        colors = self.theme_colors.get(theme_color, self.theme_colors["蓝色系"])
        
        return {
            "aspect_ratio": "16:9",
            "slide_width": 13.333,  # 英寸
            "slide_height": 7.5,     # 英寸
            "fonts": self.fonts,
            "font_sizes": self.font_sizes,
            "colors": colors,
            "margins": {
                "left": 0.8,
                "right": 0.8,
                "top": 0.6,
                "bottom": 0.6
            }
        }
    
    async def _create_pptx_file(
        self,
        topic: str,
        pages: List[Dict],
        style: Dict,
        theme_color: str,
        task_dir: str
    ) -> str:
        """创建PPTX文件 - 严格遵循兼容性标准"""
        
        try:
            from pptx import Presentation
            from pptx.util import Inches, Pt, Emu
            from pptx.dml.color import RGBColor
            from pptx.enum.text import PP_ALIGN
            from pptx.enum.shapes import MSO_SHAPE
        except ImportError:
            # python-pptx未安装，生成HTML预览替代
            return await self._create_html_preview(topic, pages, style, task_dir)
        
        # 创建演示文稿
        prs = Presentation()
        
        # 设置16:9比例
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)
        
        # 获取颜色
        colors = self.theme_colors.get(theme_color, self.theme_colors["蓝色系"])
        
        # 生成每页幻灯片
        for page in pages:
            page_type = page.get("page_type", "knowledge")
            
            if page_type == "cover":
                self._add_cover_slide_v2(prs, page, colors, style)
            elif page_type == "toc":
                self._add_toc_slide_v2(prs, page, colors, style)
            elif page_type == "knowledge":
                self._add_knowledge_slide_v2(prs, page, colors, style)
            elif page_type == "exercise":
                self._add_exercise_slide_v2(prs, page, colors, style)
            elif page_type == "summary":
                self._add_summary_slide_v2(prs, page, colors, style)
            else:
                self._add_default_slide_v2(prs, page, colors, style)
        
        # 添加感谢页
        self._add_thank_you_slide_v2(prs, colors)
        
        # 保存文件
        safe_filename = self._safe_filename(topic)
        pptx_path = os.path.join(task_dir, f"{safe_filename}_课件.pptx")
        prs.save(pptx_path)
        
        return pptx_path
    
    def _add_cover_slide_v2(self, prs, page: Dict, colors: Dict, style: Dict):
        """封面页"""
        
        slide = prs.slides.add_slide(prs.slide_layouts[6])  # 空白布局
        
        # 背景 - 主色渐变效果（用矩形模拟）
        bg = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            0, 0,
            prs.slide_width, prs.slide_height
        )
        bg.fill.solid()
        bg.fill.fore_color.rgb = RGBColor(*colors["primary"])
        bg.line.fill.background()
        
        # 装饰圆形
        decor1 = slide.shapes.add_shape(
            MSO_SHAPE.OVAL,
            Inches(10), Inches(-1),
            Inches(5), Inches(5)
        )
        decor1.fill.solid()
        decor1.fill.fore_color.rgb = RGBColor(*colors["secondary"])
        decor1.line.fill.background()
        
        # 主标题
        title_box = slide.shapes.add_textbox(
            Inches(1), Inches(2.5),
            Inches(11), Inches(1.5)
        )
        tf = title_box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = page.get("main_title", "课程标题")
        p.font.size = Pt(48)
        p.font.bold = True
        p.font.color.rgb = RGBColor(255, 255, 255)
        p.font.name = style["fonts"]["chinese"]  # 微软雅黑
        p.alignment = PP_ALIGN.CENTER
        
        # 副标题
        subtitle_box = slide.shapes.add_textbox(
            Inches(1), Inches(4.2),
            Inches(11), Inches(1)
        )
        tf = subtitle_box.text_frame
        p = tf.paragraphs[0]
        p.text = page.get("subtitle", "")
        p.font.size = Pt(24)
        p.font.color.rgb = RGBColor(255, 255, 255)
        p.font.name = style["fonts"]["chinese"]
        p.alignment = PP_ALIGN.CENTER
        
        # 授课信息
        info_box = slide.shapes.add_textbox(
            Inches(1), Inches(5.5),
            Inches(11), Inches(0.8)
        )
        tf = info_box.text_frame
        p = tf.paragraphs[0]
        p.text = f"{page.get('instructor_info', '授课教师')}  |  {page.get('date', '')}"
        p.font.size = Pt(18)
        p.font.color.rgb = RGBColor(255, 255, 255)
        p.font.name = style["fonts"]["chinese"]
        p.alignment = PP_ALIGN.CENTER
    
    def _add_toc_slide_v2(self, prs, page: Dict, colors: Dict, style: Dict):
        """目录页"""
        
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        
        # 顶部色条
        top_bar = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            0, 0,
            prs.slide_width, Inches(0.15)
        )
        top_bar.fill.solid()
        top_bar.fill.fore_color.rgb = RGBColor(*colors["primary"])
        top_bar.line.fill.background()
        
        # 标题
        title_box = slide.shapes.add_textbox(
            Inches(0.8), Inches(0.5),
            Inches(11), Inches(1)
        )
        tf = title_box.text_frame
        p = tf.paragraphs[0]
        p.text = page.get("core_topic", "课程目录")
        p.font.size = Pt(36)
        p.font.bold = True
        p.font.color.rgb = RGBColor(*colors["text"])
        p.font.name = style["fonts"]["chinese"]
        
        # 目录项
        toc_items = page.get("toc_items", [])
        y = 2.0
        
        for i, item in enumerate(toc_items[:8]):  # 最多8项
            # 序号圆圈
            num_box = slide.shapes.add_shape(
                MSO_SHAPE.OVAL,
                Inches(1.5), Inches(y),
                Inches(0.5), Inches(0.5)
            )
            num_box.fill.solid()
            num_box.fill.fore_color.rgb = RGBColor(*colors["primary"])
            num_box.line.fill.background()
            
            # 序号文字
            num_tf = num_box.text_frame
            num_p = num_tf.paragraphs[0]
            num_p.text = str(i + 1)
            num_p.font.size = Pt(14)
            num_p.font.bold = True
            num_p.font.color.rgb = RGBColor(255, 255, 255)
            num_p.alignment = PP_ALIGN.CENTER
            
            # 目录文字
            item_box = slide.shapes.add_textbox(
                Inches(2.2), Inches(y + 0.05),
                Inches(9), Inches(0.5)
            )
            tf = item_box.text_frame
            p = tf.paragraphs[0]
            p.text = item
            p.font.size = Pt(20)
            p.font.color.rgb = RGBColor(*colors["text"])
            p.font.name = style["fonts"]["chinese"]
            
            y += 0.65
    
    def _add_knowledge_slide_v2(self, prs, page: Dict, colors: Dict, style: Dict):
        """知识点页"""
        
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        
        # 顶部色条
        top_bar = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            0, 0,
            prs.slide_width, Inches(0.15)
        )
        top_bar.fill.solid()
        top_bar.fill.fore_color.rgb = RGBColor(*colors["primary"])
        top_bar.line.fill.background()
        
        # 左侧装饰条
        left_bar = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            0, Inches(0.15),
            Inches(0.1), prs.slide_height - Inches(0.15)
        )
        left_bar.fill.solid()
        left_bar.fill.fore_color.rgb = RGBColor(*colors["secondary"])
        left_bar.line.fill.background()
        
        # 标题
        title_box = slide.shapes.add_textbox(
            Inches(0.5), Inches(0.4),
            Inches(12), Inches(0.8)
        )
        tf = title_box.text_frame
        p = tf.paragraphs[0]
        p.text = page.get("core_topic", "知识点")
        p.font.size = Pt(32)
        p.font.bold = True
        p.font.color.rgb = RGBColor(*colors["text"])
        p.font.name = style["fonts"]["chinese"]
        
        # 核心要点
        key_points = page.get("key_points", [])
        y = 1.5
        
        for point in key_points[:5]:  # 最多5条
            # 要点圆点
            bullet = slide.shapes.add_shape(
                MSO_SHAPE.OVAL,
                Inches(0.8), Inches(y + 0.15),
                Inches(0.15), Inches(0.15)
            )
            bullet.fill.solid()
            bullet.fill.fore_color.rgb = RGBColor(*colors["accent"])
            bullet.line.fill.background()
            
            # 要点文字
            point_box = slide.shapes.add_textbox(
                Inches(1.1), Inches(y),
                Inches(11), Inches(0.7)
            )
            tf = point_box.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = point
            p.font.size = Pt(20)
            p.font.color.rgb = RGBColor(*colors["text"])
            p.font.name = style["fonts"]["chinese"]
            p.space_after = Pt(8)
            
            y += 0.75
        
        # 案例分析（如果有）
        case_study = page.get("case_study", "")
        if case_study:
            case_box = slide.shapes.add_textbox(
                Inches(0.8), Inches(5.5),
                Inches(11.5), Inches(1.5)
            )
            tf = case_box.text_frame
            tf.word_wrap = True
            
            p = tf.paragraphs[0]
            p.text = "📋 案例分析"
            p.font.size = Pt(16)
            p.font.bold = True
            p.font.color.rgb = RGBColor(*colors["primary"])
            p.font.name = style["fonts"]["chinese"]
            
            p = tf.add_paragraph()
            p.text = case_study
            p.font.size = Pt(14)
            p.font.color.rgb = RGBColor(*colors["text"])
            p.font.name = style["fonts"]["chinese"]
    
    def _add_exercise_slide_v2(self, prs, page: Dict, colors: Dict, style: Dict):
        """习题页"""
        
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        
        # 顶部色条
        top_bar = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            0, 0,
            prs.slide_width, Inches(0.15)
        )
        top_bar.fill.solid()
        top_bar.fill.fore_color.rgb = RGBColor(*colors["accent"])
        top_bar.line.fill.background()
        
        # 标题
        title_box = slide.shapes.add_textbox(
            Inches(0.5), Inches(0.4),
            Inches(12), Inches(0.8)
        )
        tf = title_box.text_frame
        p = tf.paragraphs[0]
        p.text = page.get("core_topic", "课堂练习")
        p.font.size = Pt(32)
        p.font.bold = True
        p.font.color.rgb = RGBColor(*colors["text"])
        p.font.name = style["fonts"]["chinese"]
        
        # 习题内容
        exercises = page.get("exercises", [])
        y = 1.5
        
        for i, exercise in enumerate(exercises[:3]):  # 最多3题
            # 题号
            q_box = slide.shapes.add_textbox(
                Inches(0.8), Inches(y),
                Inches(11), Inches(0.5)
            )
            tf = q_box.text_frame
            p = tf.paragraphs[0]
            p.text = f"{i + 1}. {exercise.get('question', '')}"
            p.font.size = Pt(20)
            p.font.bold = True
            p.font.color.rgb = RGBColor(*colors["text"])
            p.font.name = style["fonts"]["chinese"]
            y += 0.5
            
            # 选项
            options = exercise.get("options", [])
            for opt in options[:4]:
                opt_box = slide.shapes.add_textbox(
                    Inches(1.2), Inches(y),
                    Inches(10), Inches(0.4)
                )
                tf = opt_box.text_frame
                p = tf.paragraphs[0]
                p.text = opt
                p.font.size = Pt(16)
                p.font.color.rgb = RGBColor(*colors["text"])
                p.font.name = style["fonts"]["chinese"]
                y += 0.35
            
            y += 0.3
    
    def _add_summary_slide_v2(self, prs, page: Dict, colors: Dict, style: Dict):
        """总结页"""
        
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        
        # 背景
        bg = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            0, 0,
            prs.slide_width, prs.slide_height
        )
        bg.fill.solid()
        bg.fill.fore_color.rgb = RGBColor(*colors["primary"])
        bg.line.fill.background()
        
        # 标题
        title_box = slide.shapes.add_textbox(
            Inches(0.5), Inches(0.5),
            Inches(12), Inches(1)
        )
        tf = title_box.text_frame
        p = tf.paragraphs[0]
        p.text = page.get("core_topic", "课程总结")
        p.font.size = Pt(36)
        p.font.bold = True
        p.font.color.rgb = RGBColor(255, 255, 255)
        p.font.name = style["fonts"]["chinese"]
        
        # 总结要点
        review_items = page.get("knowledge_review", [])
        y = 2.0
        
        for item in review_items[:5]:
            check = slide.shapes.add_shape(
                MSO_SHAPE.OVAL,
                Inches(1), Inches(y + 0.1),
                Inches(0.3), Inches(0.3)
            )
            check.fill.solid()
            check.fill.fore_color.rgb = RGBColor(46, 204, 113)  # 绿色
            check.line.fill.background()
            
            item_box = slide.shapes.add_textbox(
                Inches(1.5), Inches(y),
                Inches(10), Inches(0.6)
            )
            tf = item_box.text_frame
            p = tf.paragraphs[0]
            p.text = f"✓ {item}"
            p.font.size = Pt(20)
            p.font.color.rgb = RGBColor(255, 255, 255)
            p.font.name = style["fonts"]["chinese"]
            y += 0.6
        
        # 课后作业
        homework = page.get("homework", "")
        if homework:
            hw_box = slide.shapes.add_textbox(
                Inches(1), Inches(5.5),
                Inches(11), Inches(1)
            )
            tf = hw_box.text_frame
            p = tf.paragraphs[0]
            p.text = f"📝 课后作业: {homework}"
            p.font.size = Pt(18)
            p.font.color.rgb = RGBColor(255, 255, 255)
            p.font.name = style["fonts"]["chinese"]
    
    def _add_default_slide_v2(self, prs, page: Dict, colors: Dict, style: Dict):
        """默认页"""
        
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        
        # 顶部色条
        top_bar = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            0, 0,
            prs.slide_width, Inches(0.15)
        )
        top_bar.fill.solid()
        top_bar.fill.fore_color.rgb = RGBColor(*colors["primary"])
        top_bar.line.fill.background()
        
        # 标题
        title_box = slide.shapes.add_textbox(
            Inches(0.5), Inches(0.4),
            Inches(12), Inches(1)
        )
        tf = title_box.text_frame
        p = tf.paragraphs[0]
        p.text = page.get("core_topic", "")
        p.font.size = Pt(32)
        p.font.bold = True
        p.font.color.rgb = RGBColor(*colors["text"])
        p.font.name = style["fonts"]["chinese"]
        
        # 内容
        content_box = slide.shapes.add_textbox(
            Inches(0.8), Inches(1.5),
            Inches(11.5), Inches(5)
        )
        tf = content_box.text_frame
        tf.word_wrap = True
        
        for i, point in enumerate(page.get("key_points", [])[:5]):
            if i == 0:
                p = tf.paragraphs[0]
            else:
                p = tf.add_paragraph()
            p.text = f"• {point}"
            p.font.size = Pt(20)
            p.font.color.rgb = RGBColor(*colors["text"])
            p.font.name = style["fonts"]["chinese"]
            p.space_after = Pt(12)
    
    def _add_thank_you_slide_v2(self, prs, colors: Dict):
        """感谢页"""
        
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        
        # 背景
        bg = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            0, 0,
            prs.slide_width, prs.slide_height
        )
        bg.fill.solid()
        bg.fill.fore_color.rgb = RGBColor(*colors["text"])
        bg.line.fill.background()
        
        # 感谢文字
        title_box = slide.shapes.add_textbox(
            Inches(0.5), Inches(2.8),
            Inches(12), Inches(1.5)
        )
        tf = title_box.text_frame
        p = tf.paragraphs[0]
        p.text = "感谢聆听"
        p.font.size = Pt(72)
        p.font.bold = True
        p.font.color.rgb = RGBColor(255, 255, 255)
        p.font.name = self.fonts["chinese"]
        p.alignment = PP_ALIGN.CENTER
        
        # 副标题
        subtitle_box = slide.shapes.add_textbox(
            Inches(0.5), Inches(4.5),
            Inches(12), Inches(1)
        )
        tf = subtitle_box.text_frame
        p = tf.paragraphs[0]
        p.text = "欢迎提问与交流"
        p.font.size = Pt(28)
        p.font.color.rgb = RGBColor(189, 195, 199)
        p.font.name = self.fonts["chinese"]
        p.alignment = PP_ALIGN.CENTER
    
    async def _create_html_preview(
        self,
        topic: str,
        pages: List[Dict],
        style: Dict,
        task_dir: str
    ) -> str:
        """创建HTML预览（当python-pptx不可用时）"""
        
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{topic} - 课件预览</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: '微软雅黑', Arial, sans-serif; background: #1a1f4e; padding: 20px; }}
        .slide {{ width: 960px; height: 540px; margin: 20px auto; background: white; border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); overflow: hidden; position: relative; }}
        .slide-header {{ height: 8px; background: linear-gradient(90deg, #3498db, #2ecc71); }}
        .slide-content {{ padding: 30px; }}
        .slide-title {{ font-size: 28px; color: #2c3e50; margin-bottom: 20px; font-weight: bold; }}
        .slide-body {{ font-size: 18px; color: #34495e; line-height: 1.8; }}
        .slide-body li {{ margin: 10px 0; }}
        .cover-slide {{ background: linear-gradient(135deg, #3498db, #2980b9); color: white; text-align: center; display: flex; flex-direction: column; justify-content: center; height: 100%; }}
        .cover-slide .title {{ font-size: 48px; margin-bottom: 20px; }}
        .cover-slide .subtitle {{ font-size: 24px; opacity: 0.9; }}
        .thank-slide {{ background: #2c3e50; color: white; text-align: center; display: flex; flex-direction: column; justify-content: center; height: 100%; }}
        .thank-slide .text {{ font-size: 64px; margin-bottom: 20px; }}
        h1 {{ text-align: center; color: white; margin: 20px 0; }}
    </style>
</head>
<body>
    <h1>{topic} - 课件预览</h1>
"""
        
        for i, page in enumerate(pages):
            page_type = page.get("page_type", "knowledge")
            
            if page_type == "cover":
                html_content += f"""
    <div class="slide">
        <div class="slide-content cover-slide">
            <div class="title">{page.get('main_title', '')}</div>
            <div class="subtitle">{page.get('subtitle', '')}</div>
            <div style="margin-top: 40px; font-size: 18px;">{page.get('instructor_info', '')} | {page.get('date', '')}</div>
        </div>
    </div>
"""
            elif page_type == "toc":
                items = page.get("toc_items", [])
                html_content += f"""
    <div class="slide">
        <div class="slide-header"></div>
        <div class="slide-content">
            <div class="slide-title">{page.get('core_topic', '目录')}</div>
            <div class="slide-body">
                <ol style="font-size: 22px;">
                    {"".join([f"<li>{item}</li>" for item in items])}
                </ol>
            </div>
        </div>
    </div>
"""
            elif page_type == "summary":
                html_content += f"""
    <div class="slide">
        <div class="slide-content cover-slide">
            <div class="title" style="font-size: 36px;">{page.get('core_topic', '总结')}</div>
            <div class="subtitle" style="font-size: 20px; text-align: left; max-width: 600px; margin: 20px auto;">
                {"<br>".join([f"✓ {item}" for item in page.get('knowledge_review', [])])}
            </div>
        </div>
    </div>
"""
            else:
                points = page.get("key_points", [])
                html_content += f"""
    <div class="slide">
        <div class="slide-header"></div>
        <div class="slide-content">
            <div class="slide-title">{page.get('core_topic', '')}</div>
            <div class="slide-body">
                <ul>
                    {"".join([f"<li>{point}</li>" for point in points])}
                </ul>
            </div>
        </div>
    </div>
"""
        
        html_content += """
    <div class="slide">
        <div class="slide-content thank-slide">
            <div class="text">感谢聆听</div>
            <div style="font-size: 24px; opacity: 0.8;">欢迎提问与交流</div>
        </div>
    </div>
</body>
</html>"""
        
        html_path = os.path.join(task_dir, f"{self._safe_filename(topic)}_preview.html")
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return html_path
    
    async def _validate_pptx(self, file_path: str) -> Dict:
        """校验PPTX文件"""
        
        result = {
            "valid": False,
            "error": None,
            "file_size": 0,
            "pages": 0
        }
        
        if not os.path.exists(file_path):
            result["error"] = "文件不存在"
            return result
        
        result["file_size"] = os.path.getsize(file_path)
        
        # 检查文件大小
        if result["file_size"] < 1000:  # 小于1KB
            result["error"] = "文件过小，可能已损坏"
            return result
        
        # 尝试读取验证
        try:
            from pptx import Presentation
            prs = Presentation(file_path)
            result["pages"] = len(prs.slides)
            
            # 基本内容检查
            for slide in prs.slides:
                if not slide.shapes:
                    result["error"] = "存在空白幻灯片"
                    break
            else:
                result["valid"] = True
                
        except Exception as e:
            result["error"] = f"读取失败: {str(e)}"
        
        return result


# ==================== 便捷函数 ====================

def quick_generate(
    topic: str,
    audience: str = "大学生",
    duration: int = 45,
    theme_color: str = "蓝色系",
    provider: str = None
) -> str:
    """
    快速创建生成任务
    
    Returns:
        task_id: 任务ID
    """
    generator = CoursewareGeneratorV2()
    return generator.create_task(
        topic=topic,
        audience=audience,
        duration=duration,
        theme_color=theme_color,
        provider=provider
    )


# ==================== 导出 ====================
__all__ = [
    "CoursewareGeneratorV2",
    "quick_generate"
]
