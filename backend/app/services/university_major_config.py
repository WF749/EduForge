# 大学全专业适配配置文件
# 内置13大学科门类、主流一级专业的教学规范和认证要求

class UniversityMajorConfig:
    """大学全专业适配配置"""
    
    # 13大学科门类
    DISCIPLINES = {
        "01": "哲学",
        "02": "经济学",
        "03": "法学",
        "04": "教育学",
        "05": "文学",
        "06": "历史学",
        "07": "理学",
        "08": "工学",
        "09": "农学",
        "10": "医学",
        "11": "管理学",
        "12": "艺术学",
        "13": "交叉学科"
    }
    
    # 主流一级专业配置
    MAJOR_CONFIGS = {
        # 工学类专业
        "计算机科学与技术": {
            "discipline": "08",
            "certification": "工程教育认证",
            "core_courses": ["数据结构", "算法设计与分析", "计算机组成原理", "操作系统", "计算机网络", "数据库系统"],
            "industry_standards": ["ACM/IEEE CS Curriculum", "软件工程国家标准"],
            "course_ideology": ["大国工匠精神", "网络安全意识", "人工智能伦理", "创新思维"],
            "practice_ratio": 0.3,
            "assessment_weights": {
                "attendance": 0.05,
                "class_discussion": 0.15,
                "homework": 0.2,
                "lab_report": 0.25,
                "final_exam": 0.35
            }
        },
        "软件工程": {
            "discipline": "08",
            "certification": "工程教育认证",
            "core_courses": ["软件工程导论", "软件需求工程", "软件设计与体系结构", "软件测试", "软件项目管理"],
            "industry_standards": ["ISO 9001", "CMMI", "软件工程国家标准"],
            "course_ideology": ["工匠精神", "团队协作", "软件伦理", "质量意识"],
            "practice_ratio": 0.4,
            "assessment_weights": {
                "attendance": 0.05,
                "class_discussion": 0.1,
                "homework": 0.15,
                "project": 0.4,
                "final_exam": 0.3
            }
        },
        "电子信息工程": {
            "discipline": "08",
            "certification": "工程教育认证",
            "core_courses": ["电路分析", "模拟电子技术", "数字电子技术", "信号与系统", "通信原理"],
            "industry_standards": ["IEEE standards", "电子行业国家标准"],
            "course_ideology": ["严谨求实", "创新精神", "国防意识", "环保理念"],
            "practice_ratio": 0.35,
            "assessment_weights": {
                "attendance": 0.05,
                "class_discussion": 0.1,
                "homework": 0.2,
                "lab_report": 0.3,
                "final_exam": 0.35
            }
        },
        
        # 医学类专业
        "临床医学": {
            "discipline": "10",
            "certification": "医学专业认证",
            "core_courses": ["解剖学", "生理学", "生物化学", "病理学", "药理学", "内科学", "外科学"],
            "industry_standards": ["国家临床诊疗指南", "医师资格考试大纲"],
            "course_ideology": ["医者仁心", "医德医风", "人文关怀", "生命伦理"],
            "practice_ratio": 0.5,
            "assessment_weights": {
                "attendance": 0.05,
                "class_discussion": 0.1,
                "homework": 0.15,
                "clinical_practice": 0.4,
                "final_exam": 0.3
            }
        },
        "护理学": {
            "discipline": "10",
            "certification": "医学专业认证",
            "core_courses": ["基础护理学", "内科护理学", "外科护理学", "儿科护理学", "妇产科护理学"],
            "industry_standards": ["护理专业标准", "护士执业资格考试大纲"],
            "course_ideology": ["南丁格尔精神", "人文关怀", "职业操守", "团队协作"],
            "practice_ratio": 0.55,
            "assessment_weights": {
                "attendance": 0.05,
                "class_discussion": 0.1,
                "homework": 0.15,
                "clinical_practice": 0.45,
                "final_exam": 0.25
            }
        },
        
        # 师范类专业
        "学前教育": {
            "discipline": "04",
            "certification": "师范类专业认证",
            "core_courses": ["学前教育学", "学前心理学", "学前卫生学", "幼儿游戏理论", "幼儿园课程"],
            "industry_standards": ["幼儿园教师专业标准", "学前教育专业教学质量标准"],
            "course_ideology": ["师德师风", "教育情怀", "儿童发展", "社会责任"],
            "practice_ratio": 0.4,
            "assessment_weights": {
                "attendance": 0.05,
                "class_discussion": 0.15,
                "homework": 0.2,
                "teaching_practice": 0.35,
                "final_exam": 0.25
            }
        },
        "小学教育": {
            "discipline": "04",
            "certification": "师范类专业认证",
            "core_courses": ["小学教育学", "儿童心理学", "小学语文教学法", "小学数学教学法", "小学教育研究方法"],
            "industry_standards": ["小学教师专业标准", "小学教育专业教学质量标准"],
            "course_ideology": ["师德师风", "教育情怀", "学生发展", "终身学习"],
            "practice_ratio": 0.4,
            "assessment_weights": {
                "attendance": 0.05,
                "class_discussion": 0.15,
                "homework": 0.2,
                "teaching_practice": 0.35,
                "final_exam": 0.25
            }
        },
        
        # 经管类专业
        "工商管理": {
            "discipline": "11",
            "certification": "经管类专业认证",
            "core_courses": ["管理学", "微观经济学", "宏观经济学", "市场营销", "财务管理", "人力资源管理"],
            "industry_standards": ["工商管理专业教学质量标准", "职业资格考试大纲"],
            "course_ideology": ["商业伦理", "社会责任", "创新精神", "全球视野"],
            "practice_ratio": 0.3,
            "assessment_weights": {
                "attendance": 0.05,
                "class_discussion": 0.15,
                "homework": 0.2,
                "case_study": 0.25,
                "final_exam": 0.35
            }
        },
        "金融学": {
            "discipline": "02",
            "certification": "经管类专业认证",
            "core_courses": ["金融学", "金融市场学", "国际金融", "商业银行经营管理", "投资学"],
            "industry_standards": ["金融学专业教学质量标准", "金融从业资格考试大纲"],
            "course_ideology": ["诚信守法", "风险意识", "社会责任", "专业精神"],
            "practice_ratio": 0.3,
            "assessment_weights": {
                "attendance": 0.05,
                "class_discussion": 0.15,
                "homework": 0.2,
                "case_study": 0.25,
                "final_exam": 0.35
            }
        },
        
        # 理学类专业
        "数学与应用数学": {
            "discipline": "07",
            "certification": "理学专业认证",
            "core_courses": ["数学分析", "高等代数", "解析几何", "常微分方程", "概率论与数理统计"],
            "industry_standards": ["数学专业教学质量标准", "教师职业资格考试大纲"],
            "course_ideology": ["科学精神", "逻辑思维", "创新意识", "严谨求实"],
            "practice_ratio": 0.25,
            "assessment_weights": {
                "attendance": 0.05,
                "class_discussion": 0.1,
                "homework": 0.3,
                "problem_solving": 0.25,
                "final_exam": 0.3
            }
        },
        "物理学": {
            "discipline": "07",
            "certification": "理学专业认证",
            "core_courses": ["力学", "热学", "电磁学", "光学", "近代物理学"],
            "industry_standards": ["物理学专业教学质量标准", "教师职业资格考试大纲"],
            "course_ideology": ["科学精神", "实验探究", "创新意识", "严谨求实"],
            "practice_ratio": 0.35,
            "assessment_weights": {
                "attendance": 0.05,
                "class_discussion": 0.1,
                "homework": 0.2,
                "lab_report": 0.3,
                "final_exam": 0.35
            }
        },
        
        # 文学类专业
        "汉语言文学": {
            "discipline": "05",
            "certification": "文学专业认证",
            "core_courses": ["古代汉语", "现代汉语", "文学理论", "中国古代文学", "中国现当代文学"],
            "industry_standards": ["汉语言文学专业教学质量标准", "教师职业资格考试大纲"],
            "course_ideology": ["文化自信", "人文素养", "社会责任", "审美能力"],
            "practice_ratio": 0.25,
            "assessment_weights": {
                "attendance": 0.05,
                "class_discussion": 0.15,
                "homework": 0.25,
                "essay_writing": 0.25,
                "final_exam": 0.3
            }
        },
        "英语": {
            "discipline": "05",
            "certification": "文学专业认证",
            "core_courses": ["综合英语", "英语听力", "英语口语", "英语写作", "英语文学"],
            "industry_standards": ["英语专业教学质量标准", "英语专业四八级考试大纲"],
            "course_ideology": ["跨文化交流", "国际视野", "人文素养", "职业素养"],
            "practice_ratio": 0.35,
            "assessment_weights": {
                "attendance": 0.05,
                "class_discussion": 0.2,
                "homework": 0.2,
                "language_practice": 0.25,
                "final_exam": 0.3
            }
        }
    }
    
    # 通用课程类型配置
    COURSE_TYPES = {
        "理论课": {
            "teaching_method": "讲授+讨论",
            "practice_ratio": 0.2,
            "assessment_focus": "理论知识"
        },
        "实验课": {
            "teaching_method": "实验操作+指导",
            "practice_ratio": 0.8,
            "assessment_focus": "实验技能"
        },
        "实训课": {
            "teaching_method": "项目实践+指导",
            "practice_ratio": 0.9,
            "assessment_focus": "实践能力"
        },
        "研讨课": {
            "teaching_method": "小组讨论+汇报",
            "practice_ratio": 0.6,
            "assessment_focus": "创新思维"
        },
        "混合式教学": {
            "teaching_method": "线上+线下",
            "practice_ratio": 0.4,
            "assessment_focus": "综合能力"
        }
    }
    
    @classmethod
    def get_major_config(cls, major_name):
        """获取专业配置"""
        return cls.MAJOR_CONFIGS.get(major_name, {
            "discipline": "13",  # 默认交叉学科
            "certification": "通用专业认证",
            "core_courses": [],
            "industry_standards": [],
            "course_ideology": ["专业精神", "创新意识", "社会责任"],
            "practice_ratio": 0.25,
            "assessment_weights": {
                "attendance": 0.05,
                "class_discussion": 0.15,
                "homework": 0.2,
                "final_exam": 0.6
            }
        })
    
    @classmethod
    def get_course_type_config(cls, course_type):
        """获取课程类型配置"""
        return cls.COURSE_TYPES.get(course_type, cls.COURSE_TYPES["理论课"])
    
    @classmethod
    def get_discipline_name(cls, discipline_code):
        """获取学科门类名称"""
        return cls.DISCIPLINES.get(discipline_code, "交叉学科")
    
    @classmethod
    def get_all_majors(cls):
        """获取所有专业列表"""
        return list(cls.MAJOR_CONFIGS.keys())
    
    @classmethod
    def get_majors_by_discipline(cls, discipline_code):
        """按学科门类获取专业列表"""
        return [major for major, config in cls.MAJOR_CONFIGS.items() if config.get("discipline") == discipline_code]
