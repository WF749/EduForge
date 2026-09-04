"""教学策略智能体服务 - 多智能体协作架构中的策略规划角色

创新亮点：
1. 教学场景感知 - 根据学科+学段自动匹配教学策略
2. 多智能体协作 - 策略智能体、内容智能体、评估智能体协同工作
3. 教学法知识图谱 - 内置布鲁姆认知层次、多元智能等教学理论
"""
from typing import Dict, List, Optional


class TeachingStrategyService:
    """教学策略智能体 - 基于教学法理论的智能策略推荐"""

    def __init__(self):
        # 布鲁姆认知层次模型
        self.bloom_taxonomy = {
            "remember": {"level": 1, "label": "识记", "verbs": ["列举", "识别", "回忆", "描述"]},
            "understand": {"level": 2, "label": "理解", "verbs": ["解释", "概括", "分类", "比较"]},
            "apply": {"level": 3, "label": "应用", "verbs": ["运用", "计算", "执行", "实施"]},
            "analyze": {"level": 4, "label": "分析", "verbs": ["区分", "组织", "推断", "解构"]},
            "evaluate": {"level": 5, "label": "评价", "verbs": ["判断", "评估", "论证", "反思"]},
            "create": {"level": 6, "label": "创造", "verbs": ["设计", "构建", "创作", "发明"]}
        }

        # 学科教学策略知识库
        self.subject_strategies = {
            "语文": {
                "methods": ["情境教学法", "读写结合法", "群文阅读", "思维导图"],
                "interaction": ["朗读展示", "角色扮演", "小组讨论", "写作分享"],
                "media": ["经典朗诵视频", "作者背景图文", "思维导图模板"]
            },
            "数学": {
                "methods": ["问题驱动法", "数形结合", "变式训练", "建模思想"],
                "interaction": ["动手操作", "几何画板演示", "小组竞赛", "错题分析"],
                "media": ["GeoGebra动画", "数据可视化", "实际应用案例"]
            },
            "英语": {
                "methods": ["任务型教学", "情境交际法", "沉浸式学习", "语块教学"],
                "interaction": ["Pair work", "Role play", "听力竞猜", "英语角"],
                "media": ["原版视频片段", "语音对比音频", "文化背景图片"]
            },
            "物理": {
                "methods": ["实验探究法", "物理建模", "类比推理", "STS教学"],
                "interaction": ["演示实验", "分组实验", "物理游戏", "生活现象分析"],
                "media": ["实验视频", "物理仿真动画", "生活实例图片"]
            },
            "化学": {
                "methods": ["实验探究法", "微观-宏观-符号三重表征", "绿色化学理念"],
                "interaction": ["分组实验", "模型搭建", "化学魔术", "案例讨论"],
                "media": ["分子动画", "实验操作视频", "元素周期表互动"]
            },
            "生物": {
                "methods": ["探究式学习", "概念图教学", "案例分析", "模型构建"],
                "interaction": ["显微镜观察", "标本制作", "辩论赛", "生态调查"],
                "media": ["细胞3D动画", "生态系统模拟", "基因工程流程图"]
            },
            "历史": {
                "methods": ["史料教学法", "时空观念培养", "历史解释", "比较分析"],
                "interaction": ["角色扮演", "历史辩论", "时间轴制作", "史料分析"],
                "media": ["历史地图", "纪录片片段", "文物图片"]
            },
            "地理": {
                "methods": ["地图教学法", "案例教学", "区域比较", "实地考察"],
                "interaction": ["地图绘制", "GIS操作", "天气预报模拟", "地理竞赛"],
                "media": ["卫星影像", "地形3D模型", "气候数据图表"]
            },
            "信息技术": {
                "methods": ["项目式学习", "翻转课堂", "任务驱动法", "游戏化学习"],
                "interaction": ["编程实践", "小组项目", "代码审查", "作品展示"],
                "media": ["代码演示动画", "流程图", "技术架构图"]
            }
        }

        # 学段特征
        self.stage_features = {
            "小学": {
                "attention_span": 15,
                "style": "趣味性强、游戏化、直观形象",
                "interaction_ratio": 0.5,
                "cognitive_levels": ["remember", "understand", "apply"]
            },
            "初中": {
                "attention_span": 25,
                "style": "启发探究、联系生活、循序渐进",
                "interaction_ratio": 0.4,
                "cognitive_levels": ["understand", "apply", "analyze"]
            },
            "高中": {
                "attention_span": 35,
                "style": "深度思考、知识系统化、素养导向",
                "interaction_ratio": 0.3,
                "cognitive_levels": ["apply", "analyze", "evaluate"]
            },
            "大学": {
                "attention_span": 45,
                "style": "理论深入、实践结合、创新思维",
                "interaction_ratio": 0.3,
                "cognitive_levels": ["analyze", "evaluate", "create"]
            }
        }

    def analyze_teaching_scene(self, topic: str, audience: str, 
                                subject: str = "", duration: int = 45) -> Dict:
        """教学场景感知分析 - 自动推荐教学策略"""
        # 自动检测学段
        stage = self._detect_stage(audience)
        stage_info = self.stage_features.get(stage, self.stage_features["高中"])

        # 自动检测学科
        if not subject:
            subject = self._detect_subject(topic)
        subject_info = self.subject_strategies.get(subject, {})

        # 推荐认知层次
        bloom_levels = [self.bloom_taxonomy[l] for l in stage_info["cognitive_levels"]]

        # 计算互动环节数量
        interaction_count = max(2, int(duration / 15 * stage_info["interaction_ratio"]))

        # 构建教学策略推荐
        strategy = {
            "scene_analysis": {
                "detected_stage": stage,
                "detected_subject": subject,
                "attention_span": stage_info["attention_span"],
                "style_recommendation": stage_info["style"]
            },
            "teaching_methods": subject_info.get("methods", ["讲授法", "讨论法"])[:3],
            "interaction_designs": subject_info.get("interaction", ["小组讨论", "课堂提问"])[:interaction_count],
            "recommended_media": subject_info.get("media", ["图文并茂"])[:3],
            "cognitive_objectives": [{
                "level": bl["label"],
                "action_verbs": bl["verbs"][:2]
            } for bl in bloom_levels],
            "time_allocation": self._plan_time_allocation(duration, stage_info),
            "assessment_suggestions": self._generate_assessment(stage, subject)
        }

        return strategy

    def get_strategy_prompt_injection(self, topic: str, audience: str,
                                      subject: str = "", duration: int = 45) -> str:
        """生成策略注入提示词 - 供其他智能体（内容/课件）使用"""
        strategy = self.analyze_teaching_scene(topic, audience, subject, duration)
        
        scene = strategy["scene_analysis"]
        prompt = f"""【教学策略智能体建议】
学科: {scene['detected_subject']} | 学段: {scene['detected_stage']} | 注意力时长: {scene['attention_span']}分钟
教学风格建议: {scene['style_recommendation']}
推荐教学方法: {', '.join(strategy['teaching_methods'])}
互动环节设计: {', '.join(strategy['interaction_designs'])}
推荐多媒体: {', '.join(strategy['recommended_media'])}
认知目标层次: {' → '.join([obj['level'] for obj in strategy['cognitive_objectives']])}
时间分配: {' | '.join([f"{k}:{v}分钟" for k, v in strategy['time_allocation'].items()])}
"""
        return prompt

    def _detect_stage(self, audience: str) -> str:
        """从受众描述中检测学段"""
        if any(kw in audience for kw in ["小学", "儿童", "少儿", "6-12"]):
            return "小学"
        if any(kw in audience for kw in ["初中", "初一", "初二", "初三", "七年级", "八年级", "九年级"]):
            return "初中"
        if any(kw in audience for kw in ["高中", "高一", "高二", "高三"]):
            return "高中"
        if any(kw in audience for kw in ["大学", "大一", "大二", "大三", "大四", "研究生", "本科", "专业"]):
            return "大学"
        return "高中"

    def _detect_subject(self, topic: str) -> str:
        """从主题中检测学科"""
        subject_keywords = {
            "语文": ["语文", "作文", "古诗", "阅读", "文言文", "散文", "小说", "诗歌", "鲁迅"],
            "数学": ["数学", "方程", "函数", "几何", "代数", "概率", "微积分", "矩阵"],
            "英语": ["英语", "English", "语法", "词汇", "阅读理解", "写作"],
            "物理": ["物理", "力学", "电学", "光学", "热学", "运动", "牛顿", "电磁"],
            "化学": ["化学", "元素", "反应", "方程式", "有机", "无机", "酸碱"],
            "生物": ["生物", "细胞", "基因", "遗传", "生态", "进化", "光合作用"],
            "历史": ["历史", "朝代", "战争", "革命", "文明", "改革"],
            "地理": ["地理", "气候", "地形", "人口", "城市", "河流"],
            "信息技术": ["编程", "Python", "Java", "算法", "数据结构", "人工智能", "计算机", "代码"]
        }
        for subject, keywords in subject_keywords.items():
            if any(kw in topic for kw in keywords):
                return subject
        return "综合"

    def _plan_time_allocation(self, duration: int, stage_info: Dict) -> Dict:
        """智能分配教学时间"""
        ratio = stage_info["interaction_ratio"]
        intro = max(3, int(duration * 0.1))
        summary = max(3, int(duration * 0.1))
        interaction = int((duration - intro - summary) * ratio)
        teaching = duration - intro - summary - interaction
        return {
            "导入": intro,
            "新授": teaching,
            "互动": interaction,
            "总结": summary
        }

    def _generate_assessment(self, stage: str, subject: str) -> List[str]:
        """生成评估建议"""
        base = ["课堂提问", "小结反馈"]
        if stage in ["小学", "初中"]:
            base += ["课堂小测", "学习单完成情况"]
        else:
            base += ["思维导图绘制", "案例分析报告"]
        return base[:3]


# 实例化
teaching_strategy_service = TeachingStrategyService()
