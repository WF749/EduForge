"""PPT生成Prompt模板库 - 封装全场景Prompt模板"""

# 设计思路参考了社区开源的教学设计实现，核心代码为本项目自主编写

class PPTPromptTemplates:
    """PPT生成Prompt模板类"""

    @staticmethod
    def generate_cover_prompt(topic, audience, duration, subject, teaching_content=""):
        """生成封面页Prompt"""
        return f"""
请为主题为'{topic}'、面向{audience}的{subject}课程生成封面页的详细内容。

如果提供了教学内容描述，请根据描述提取相关信息：
{teaching_content if teaching_content else '无'}

要求：
1. 主标题：简洁明了，突出课程主题（≤20字）
2. 副标题：补充说明课程内容或目标（≤30字）
3. 授课人信息：教师姓名/机构（可选）
4. 视觉元素提示：适合课程主题的图片或图标建议

请以JSON格式输出，包含以下字段：
- page_num：页码
- page_type：页面类型
- core_topic：核心主题
- main_title：主标题
- subtitle：副标题
- instructor_info：授课人信息
- visual_elelements：视觉元素提示
- notes：讲师备注
        """

    @staticmethod
    def generate_toc_prompt(topic, audience, duration, outline, teaching_content=""):
        """生成目录页Prompt"""
        # 提取目录项
        toc_items = [page['core_topic'] for page in outline if page['page_type'] not in ['cover', 'toc']]
        toc_items_str = '\n'.join(toc_items)
        
        return f"""
请为主题为'{topic}'、面向{audience}的课程生成目录页的详细内容。

课程大纲：
{toc_items_str}

如果提供了教学内容描述，请根据描述提取相关信息：
{teaching_content if teaching_content else '无'}

要求：
1. 目录标题：清晰明了
2. 目录项：列出课程核心模块，与后续页面完全对应
3. 视觉元素提示：适合目录页的排版建议

请以JSON格式输出，包含以下字段：
- page_num：页码
- page_type：页面类型
- core_topic：核心主题
- toc_items：目录项列表
- visual_elelements：视觉元素提示
- notes：讲师备注
        """

    @staticmethod
    def generate_knowledge_prompt(topic, audience, duration, subject, core_topic, content_outline, key_points, teaching_content=""):
        """生成知识点页Prompt"""
        key_points_str = ', '.join(key_points) if key_points else '无'
        
        return f"""
请为主题为'{topic}'、面向{audience}的{subject}课程生成知识点页的详细内容。

核心知识点：{core_topic}
内容大纲：
{chr(10).join(content_outline)}

如果提供了教学内容描述，请根据描述提取相关信息：
{teaching_content if teaching_content else '无'}

要求：
1. 核心要点：每个要点≤30字，≤5条，结构清晰，逻辑连贯
2. 案例分析：贴合知识点，使用对应受众能理解的真实案例，具有启发性
3. 视觉元素提示：具体的图片或图表建议，如柱状图、饼图、流程图等
4. 讲解要点：详细的讲解方法和注意事项，帮助讲师更好地讲解该知识点
5. 动画设计：具体的动画效果建议，如淡入、飞出、强调等
6. 排版建议：详细的页面排版建议，如标题位置、内容布局等
7. 内容深度：根据受众水平，确保内容深度适中，既不过于简单也不过于复杂

请以JSON格式输出，包含以下字段：
- page_num：页码
- page_type：页面类型
- core_topic：核心主题
- key_points：核心要点列表
- case_study：案例分析
- visual_elelements：视觉元素提示
- animation_effects：动画效果建议
- layout_suggestions：排版建议
- notes：讲师备注
        """

    @staticmethod
    def generate_exercise_prompt(topic, audience, duration, subject, teaching_content=""):
        """生成互动习题页Prompt"""
        return f"""
请为主题为'{topic}'、面向{audience}的{subject}课程生成互动习题页的详细内容。

如果提供了教学内容描述，请根据描述提取相关信息：
{teaching_content if teaching_content else '无'}

要求：
1. 习题类型：选择题、填空题、简答题等
2. 题目内容：与课程核心知识点相关
3. 选项：清晰明确
4. 答案：正确答案及解析
5. 视觉元素提示：适合习题页的排版建议
6. 动画设计：适合习题页的动画效果建议
7. 排版建议：适合习题页的页面排版建议

请以JSON格式输出，包含以下字段：
- page_num：页码
- page_type：页面类型
- core_topic：核心主题
- exercises：习题列表（包含question、options、answer、explanation）
- visual_elelements：视觉元素提示
- animation_effects：动画效果建议
- layout_suggestions：排版建议
- notes：讲师备注
        """

    @staticmethod
    def generate_summary_prompt(topic, audience, duration, subject, knowledge_pages, teaching_content=""):
        """生成总结页Prompt"""
        knowledge_topics = [page['core_topic'] for page in knowledge_pages if page['page_type'] == 'knowledge']
        knowledge_topics_str = ', '.join(knowledge_topics)
        
        return f"""
请为主题为'{topic}'、面向{audience}的{subject}课程生成总结页的详细内容。

核心知识点：{knowledge_topics_str}

如果提供了教学内容描述，请根据描述提取相关信息：
{teaching_content if teaching_content else '无'}

要求：
1. 核心知识点复盘：结构化回顾本次课的核心知识点
2. 学习目标完成情况：总结学习目标的达成情况
3. 课后作业：适配受众，分基础巩固、能力提升两个层级
4. 视觉元素提示：适合总结页的排版建议
5. 动画设计：适合总结页的动画效果建议
6. 排版建议：适合总结页的页面排版建议

请以JSON格式输出，包含以下字段：
- page_num：页码
- page_type：页面类型
- core_topic：核心主题
- knowledge_review：核心知识点复盘列表
- goals_achievement：学习目标完成情况
- homework：课后作业
- visual_elelements：视觉元素提示
- animation_effects：动画效果建议
- layout_suggestions：排版建议
- notes：讲师备注
        """

    @staticmethod
    def generate_extension_prompt(topic, audience, duration, subject, teaching_content=""):
        """生成拓展页Prompt"""
        return f"""
请为主题为'{topic}'、面向{audience}的{subject}课程生成拓展页的详细内容。

如果提供了教学内容描述，请根据描述提取相关信息：
{teaching_content if teaching_content else '无'}

要求：
1. 拓展内容：贴合主题的行业前沿、拓展文献、延伸知识
2. 参考资料：推荐的相关书籍、文章、网站等
3. 实践项目：与课程内容相关的实践活动建议
4. 视觉元素提示：适合拓展页的排版建议
5. 动画设计：适合拓展页的动画效果建议
6. 排版建议：适合拓展页的页面排版建议

请以JSON格式输出，包含以下字段：
- page_num：页码
- page_type：页面类型
- core_topic：核心主题
- after_class_thoughts：拓展内容列表
- reference_materials：参考资料列表
- practice_projects：实践项目建议
- visual_elelements：视觉元素提示
- animation_effects：动画效果建议
- layout_suggestions：排版建议
- notes：讲师备注
        """

    @staticmethod
    def generate_visual_style_prompt(topic, audience, duration, subject, theme_color, style_preference):
        """生成视觉风格Prompt"""
        return f"""
请为主题为'{topic}'、面向{audience}的{subject}课程生成PPT的视觉风格规范。

主题色：{theme_color}
风格偏好：{style_preference}

要求：
1. 配色方案：主色调、辅助色、背景色
2. 字体规范：标题字体、正文字体、字号
3. 排版风格：间距、对齐方式、布局
4. 视觉元素：图标、图片、图表风格
5. 动画效果：适合教学的动画建议

请以JSON格式输出，包含以下字段：
- color_scheme：配色方案
- font_specs：字体规范
- layout_style：排版风格
- visual_elements：视觉元素建议
- animation_effects：动画效果建议
        """

    @staticmethod
    def generate_ppt_outline_prompt(topic, audience, duration, subject, key_points, teaching_goals, teaching_content=""):
        """生成PPT大纲Prompt"""
        key_points_str = ', '.join(key_points) if key_points else '无'
        knowledge_goals = ', '.join(teaching_goals.get('knowledge_goals', []))
        ability_goals = ', '.join(teaching_goals.get('ability_goals', []))
        emotional_goals = ', '.join(teaching_goals.get('emotional_goals', []))
        
        return f"""
请为主题为'{topic}'、面向{audience}的{subject}课程生成一个结构化的PPT大纲。

课程信息：
- 时长：{duration}分钟
- 核心知识点：{key_points_str}
- 教学目标：
  知识目标：{knowledge_goals}
  能力目标：{ability_goals}
  情感目标：{emotional_goals}

如果提供了教学内容描述，请根据描述提取相关信息：
{teaching_content if teaching_content else '无'}

要求：
1. 大纲必须符合课堂教学逻辑：导入→知识点拆解→案例讲解→互动练习→总结→拓展
2. 单页单核心原则：每页PPT只讲1个核心知识点
3. 必备页面：必须包含封面页、目录页、≥3个知识点页、≥1个互动习题页、≥1个总结页
4. 页面数量：根据时长合理分配，建议15分钟课程5-7页，30分钟课程8-10页，45分钟课程10-12页
5. 动画设计：为每个页面提供具体的动画效果建议，如淡入、飞出、强调等
6. 排版建议：为每个页面提供详细的页面排版建议，如标题位置、内容布局等
7. 内容深度：根据受众水平，确保内容深度适中，既不过于简单也不过于复杂
8. 逻辑连贯性：确保各页面之间逻辑连贯，过渡自然

请以JSON格式输出，包含以下字段：
- page_num：页码
- page_type：页面类型（cover/toc/knowledge/exercise/summary/extension）
- core_topic：核心主题（≤20字）
- content_outline：内容要点（≤5条，每条≤30字）
- animation_suggestions：动画效果建议
- layout_suggestions：排版建议
        """

    @staticmethod
    def generate_ppt_content_prompt(topic, audience, duration, subject, outline, theme_color, style_preference, teaching_content=""):
        """生成PPT内容Prompt"""
        outline_str = '\n'.join([f"{page['page_num']}. {page['page_type']}: {page['core_topic']}" for page in outline])
        
        return f"""
请根据以下大纲为主题为'{topic}'、面向{audience}的{subject}课程生成PPT的详细内容。

大纲：
{outline_str}

主题色：{theme_color}
风格偏好：{style_preference}

如果提供了教学内容描述，请根据描述提取相关信息：
{teaching_content if teaching_content else '无'}

要求：
1. 每页内容必须符合单页单核心原则
2. 内容要点简洁明了，每条≤30字
3. 案例分析贴合受众认知
4. 视觉元素建议具体可行
5. 动画设计：为每个页面提供适合的动画效果建议
6. 排版建议：为每个页面提供适合的页面排版建议
7. 所有内容必须符合教学规范

请以JSON格式输出，包含以下字段：
- pages：页面列表，每个页面包含page_num、page_type、core_topic、key_points、case_study、exercises、animation_effects、layout_suggestions等字段
        """
