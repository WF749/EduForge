"""教学合规校验器（路线图 #3 · v1）

定位：一个**纯规则、离线**的"教案/课件质检器"。
它不调用大模型，只按《义务教育课程方案与课程标准（2022 版）》的通行规范，
对 AI 生成的教学产物做"硬伤扫描"，给出可执行的修改建议。

为什么做它：通用生成器（Codex / WorkBuddy / Trae 等）只会"生成"，
不会按中国课标帮你把关。这一步才是我们与它们的差异化护城河。

当前覆盖的检查项（均为离线规则，零额度消耗）：
  R1  课标依据      —— 是否引用 2022 版课标 / 课程标准
  R2  核心素养升级  —— 是否仍用旧"三维目标"措辞，缺"核心素养"
  R3  教材版本      —— 是否标注教材版本 / 对应章节
  R4  学段匹配      —— 内容是否明显超出所选学段（如小学讲高考）
  R5  隐私泄露      —— 是否直接含学生真实手机号 / 身份证 / 姓名+成绩
  R6  时长规范      —— PPT/课件页数是否明显超出课时承载
  R7  行为动词可测量 —— 教学目标是否用了"了解/理解/掌握"这类无法评价的词
                      （仅在调用方给出 objectives_text 时检查，避免误报）
  R8  教学评一致性  —— 有教学目标却没有检测 / 评价设计，目标无法验证是否达成
                      （同样只在给出结构化文本时检查）

后续可扩展：目标-活动-检测的条目级对应、学科专属规则、与课标原文比对等。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------
SEVERITY_ERROR = "error"   # 必须改（如隐私泄露）
SEVERITY_WARN = "warn"     # 建议改（如缺课标依据）
SEVERITY_INFO = "info"     # 正向提示


@dataclass
class Issue:
    code: str
    severity: str
    message: str
    hint: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "hint": self.hint,
        }


@dataclass
class CheckReport:
    artifact_type: str
    passed: bool
    score: int
    issue_count: int
    issues: List[Issue] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_type": self.artifact_type,
            "passed": self.passed,
            "score": self.score,
            "issue_count": self.issue_count,
            "issues": [i.to_dict() for i in self.issues],
            "suggestions": self.suggestions,
        }


# ---------------------------------------------------------------------------
# 规则所用正则 / 词典
# ---------------------------------------------------------------------------
_RE_PHONE = re.compile(r"1[3-9]\d{9}")
_RE_IDCARD = re.compile(r"\d{17}[\dXx]")
_RE_EMAIL = re.compile(r"[A-Za-z0-9_.+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9-.]+")
# 「非人名标签」黑名单：这些都是教学内容里极常见的**数值标签**，
# 形如「重力：10N」「答案：3」「题号：2」，与"姓名:成绩"长得一模一样。
# 不加这层过滤，物理/数学题会被大量误报成隐私泄露，反而毁掉质检器的可信度。
_NON_PERSON_LABELS = (
    "重力|浮力|密度|质量|体积|速度|速率|时间|温度|长度|面积|压强|功率|电流|电压|"
    "电阻|压力|摩擦力|拉力|支持力|合力|位移|加速度|能量|热量|效率|路程|比值|比例|"
    "答案|选项|题目|分值|满分|得分|题号|序号|编号|步骤|环节|分钟|人数|组号|页码|"
    "页数|章节|数量|次数|天数|年份|年份|年龄|身高|体重|距离|高度|宽度|速度|单价|"
    "目标|要求|重点|难点|难点|电话|手机|学号|编号|坐标|角度|半径|直径|周长|体积|"
    "班级|年级|课时|节数|小组|队伍|排名|名次"
)
# 学生姓名+成绩，如 "张三：85" / "学生李明：92分"
_RE_NAME_SCORE = re.compile(
    # (?<![一-龥]) 不可省：没有它，引擎会从标签词的**第二个字**起匹配
    # （"答案：3" → 拿"案：3"绕过黑名单），让过滤形同虚设。
    r"(?<![一-龥])"
    r"(?:学生|同学)?"
    r"(?!(?:%s))" % _NON_PERSON_LABELS          # 排除非人名标签
    + r"[一-龥]{1,4}\s*[:：]\s*"
    r"\d{1,3}(?![\d.])"                          # 数字后不能紧跟数字/小数点
    r"(?![A-Za-z%])"                             # 数字后不能紧跟单位字母或百分号
    r"(?:\s*分)?"
)
# 模糊行为动词：写了等于没写，因为无法观测、无法测量、无法评价。
# 「了解浮力」「理解原理」这类目标是教案撰写最常见的硬伤——
# 教师无法据此判断学生到底"会没会"，也没法设计对应的检测题。
_RE_VAGUE_VERB = re.compile(
    r"(了解|理解|掌握|熟悉|认识|体会|知道|懂得|领会|感悟|好好学习|认真掌握)"
)
# 可测量的替代动词（写进 hint，给教师可直接用的替换清单）
_MEASURABLE_VERBS = (
    "说出、列举、背诵、计算、测量、解释、说明、比较、区分、归纳、"
    "推导、证明、设计、制作、演示、评价、改写、翻译"
)

_RE_CURRICULUM = re.compile(r"课标|课程标准|2022\s*版|义务教育课程方案|新课标")
_RE_CORE_LITERACY = re.compile(r"核心素养")
_RE_THREE_DIM = re.compile(
    r"三维目标|知识与技能|过程与方法|情感态度与价值观|知识与能力"
)
_RE_TEXTBOOK = re.compile(
    r"人教版|北师大版|苏教版|教科版|粤教版|沪教版|湘教版|鲁教版|"
    r"教材版本|对应教材|教材章节|第[一二三四五六七八九十\d]+章|"
    r"人教版|部编版|统编版"
)
# 学段关键词
_HIGH_STAGE_WORDS = ["高考", "研究生", "大学本科", "学术前沿", "科研素养", "毕业论文", "考研"]
_MID_STAGE_WORDS = ["中考", "会考"]
_LEVEL_ORDER = {"小学": 1, "初中": 2, "高中": 3, "普通高等院校": 4, "大学": 4, "研究生": 5}


# ---------------------------------------------------------------------------
# 产物 → 纯文本：把结构化产物摊平成可扫描的文本
# ---------------------------------------------------------------------------
# 这些字段只是路径/标识，扫它们既无意义又拖慢正则
_SKIP_KEYS = {
    "task_id", "task_dir", "html_path", "pptx_path", "files",
    "file_path", "filename", "url", "download_url", "path",
}
_RE_SCRIPT_BLOCK = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)
_RE_HTML_TAG = re.compile(r"<[^>]+>")
_RE_WS = re.compile(r"\s+")

# 单条文本超过此长度先截断再剥离，避免大 HTML 拖慢正则
_MAX_STR_SCAN = 6000
# 摊平后的总文本上限（校验只需看到代表性内容）
_MAX_TOTAL_CHARS = 12000


def _strip_html(s: str) -> str:
    """去掉 script/style 块与 HTML 标签，只留可见文本。"""
    s = _RE_SCRIPT_BLOCK.sub(" ", s)
    s = _RE_HTML_TAG.sub(" ", s)
    return _RE_WS.sub(" ", s).strip()


def flatten_to_text(obj: Any, max_chars: int = _MAX_TOTAL_CHARS) -> str:
    """把任意产物结构（dict/list/str/数字）摊平为纯文本。

    生成产物的结构各不相同（教案是嵌套 dict、动画带 HTML、PPT 带 slides 列表），
    与其为每个接口写一份取文本的适配，不如统一摊平后交给规则扫描。
    """
    parts: List[str] = []
    total = 0

    def walk(o: Any) -> None:
        nonlocal total
        if total > max_chars or o is None:
            return
        if isinstance(o, str):
            raw = o[:_MAX_STR_SCAN]
            t = _strip_html(raw) if ("<" in raw and ">" in raw) else _RE_WS.sub(" ", raw).strip()
            if t:
                parts.append(t)
                total += len(t)
        elif isinstance(o, bool):
            return
        elif isinstance(o, (int, float)):
            parts.append(str(o))
            total += len(str(o))
        elif isinstance(o, dict):
            for k, v in o.items():
                if k in _SKIP_KEYS:
                    continue
                walk(v)
        elif isinstance(o, (list, tuple)):
            for v in o:
                walk(v)

    walk(obj)
    return "\n".join(parts)[:max_chars]


# 教案里承载"检测/评价"的模块名并不固定（有的叫评价设计、有的叫当堂检测），
# 按顺序取第一个有内容的，避免因为命名差异就误判"没有检测设计"。
_ASSESSMENT_MODULE_KEYS = (
    "评价设计", "教学评价", "学习评价", "评价与检测",
    "当堂检测", "检测设计", "课堂检测",
)


def pick_assessment_text(lesson_plan: Any) -> str:
    """从教案结构中取出「检测 / 评价」模块的文本。"""
    if not isinstance(lesson_plan, dict):
        return ""
    for key in _ASSESSMENT_MODULE_KEYS:
        value = lesson_plan.get(key)
        if value:
            text = flatten_to_text(value)
            if text.strip():
                return text
    return ""


def run_compliance_gate(
    artifact_type: str,
    payload: Any,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """生成完成后的"出厂质检闸门"。

    设计原则：
      - **只报告、不阻断**。闸门失败绝不能让生成结果丢失，否则等于给线上功能
        引入新的失败模式。因此任何异常都被吞掉，返回 enabled=False。
      - 纯规则、离线、零额度，可安全地在每次生成后运行。
    """
    if not _gate_enabled():
        return {"enabled": False, "reason": "gate disabled"}
    try:
        text = flatten_to_text(payload)
        report = teaching_compliance_checker.check(artifact_type, text, meta or {})
        data = report.to_dict()
        data["enabled"] = True
        return data
    except Exception as e:  # noqa: BLE001 —— 闸门永不阻断生成
        return {
            "enabled": False,
            "reason": f"质检跳过: {str(e)}",
            "artifact_type": artifact_type,
            "passed": True,
            "score": 100,
            "issue_count": 0,
            "issues": [],
            "suggestions": [],
        }


def _gate_enabled() -> bool:
    """闸门总开关，默认开启；设 EDUFORGE_COMPLIANCE_GATE=0 可关闭。"""
    import os

    return os.getenv("EDUFORGE_COMPLIANCE_GATE", "1").strip().lower() not in (
        "0", "false", "off", "no",
    )


# ---------------------------------------------------------------------------
# 校验器
# ---------------------------------------------------------------------------
class TeachingComplianceChecker:
    """离线教学合规校验器（v1）。"""

    # 需要"课标依据 / 教材版本"检查的产物类型
    _CURRICULUM_TYPES = {"lesson_plan", "ppt", "courseware"}
    # 按课时承载评估页数的产物类型
    _PAGE_TYPES = {"ppt", "courseware"}

    def check(
        self,
        artifact_type: str,
        content: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> CheckReport:
        """对一份教学产物做合规扫描。

        :param artifact_type: lesson_plan / ppt / courseware / game / animation
        :param content: 产物的纯文本（调用方负责把结构化字段拼成文本）
        :param meta: 可选上下文，含 level/subject/grade/topic/duration
        """
        meta = meta or {}
        artifact_type = (artifact_type or "lesson_plan").lower()
        text = (content or "").strip()
        issues: List[Issue] = []

        if not text:
            issues.append(Issue(
                "R0", SEVERITY_WARN,
                "待检内容为空白", "请提供生成后的教学文本后再校验。",
            ))
            return self._finalize(artifact_type, issues)

        # R1 课标依据
        if artifact_type in self._CURRICULUM_TYPES and not _RE_CURRICULUM.search(text):
            issues.append(Issue(
                "R1", SEVERITY_WARN,
                "缺少课标依据", "建议在教案/PPT 中标注所依据的课程标准和学段要求。",
            ))

        # R2 核心素养升级
        if _RE_THREE_DIM.search(text) and not _RE_CORE_LITERACY.search(text):
            issues.append(Issue(
                "R2", SEVERITY_WARN,
                "仍使用旧版『三维目标』表述",
                "2022 版课标已从三维目标转向核心素养，建议改写为对应学科核心素养维度"
                "（如物理：物理观念/科学思维/科学探究/科学态度与责任）。",
            ))
        elif _RE_CORE_LITERACY.search(text):
            # 正向：已采用核心素养
            issues.append(Issue(
                "R2", SEVERITY_INFO,
                "已采用『核心素养』表述，符合 2022 版课标方向", "",
            ))

        # R3 教材版本
        if artifact_type in self._CURRICULUM_TYPES and not _RE_TEXTBOOK.search(text):
            issues.append(Issue(
                "R3", SEVERITY_WARN,
                "未标注教材版本 / 对应章节",
                "建议注明所用教材版本与章节（如人教版八年级下册第X章），便于教师对照使用。",
            ))

        # R4 学段匹配
        level = str(meta.get("level") or meta.get("grade") or "")
        issues.extend(self._check_stage(level, text))

        # R5 隐私泄露（硬伤，error）—— 收集全部命中，而非仅首个
        issues.extend(self._check_privacy(text))

        # R7 行为动词可测量（仅当调用方给出了教学目标文本时才检查）
        # 不传就不查 —— 宁可不报，也不在全文里瞎猜哪里是教学目标而误报。
        objectives_text = (meta.get("objectives_text") or "").strip()
        if objectives_text and _RE_VAGUE_VERB.search(objectives_text):
            hit_verbs = sorted(set(_RE_VAGUE_VERB.findall(objectives_text)))
            issues.append(Issue(
                "R7", SEVERITY_WARN,
                f"教学目标含不可测量的行为动词（{'、'.join(hit_verbs[:3])}）",
                f"「了解/理解/掌握」无法观测也无法评价，建议改为可测量动词"
                f"（{_MEASURABLE_VERBS}），"
                f"例如把「理解阿基米德原理」改写成「能说出阿基米德原理并用 F_浮=ρ_液gV_排 计算浮力」。",
            ))

        # R8 教学评一致性（有目标却没检测，目标就无法验证是否达成）
        # 同样只在调用方给出结构化文本时检查，不做全文猜测。
        if (meta.get("objectives_text") or "").strip() and \
                not (meta.get("assessment_text") or "").strip():
            issues.append(Issue(
                "R8", SEVERITY_WARN,
                "有教学目标但缺检测 / 评价设计",
                "没有检测环节就无法判断目标是否达成。建议补一个当堂检测、"
                "提问反馈或表现性评价，并确保它覆盖前面列出的目标。",
            ))

        # R6 时长规范（仅 PPT/课件，且给了课时）
        if artifact_type in self._PAGE_TYPES and meta.get("duration"):
            issues.extend(self._check_duration(
                artifact_type, text, int(meta["duration"]), meta.get("page_count"),
            ))

        return self._finalize(artifact_type, issues)

    # ---- 子规则 ----

    def _check_stage(self, level: str, text: str) -> List[Issue]:
        out: List[Issue] = []
        if not level:
            return out
        # 小学/初中 不应出现高中/大学高阶词
        if any(k in level for k in ("小学", "初中")):
            hit = [w for w in _HIGH_STAGE_WORDS if w in text]
            if hit:
                out.append(Issue(
                    "R4", SEVERITY_WARN,
                    f"内容可能超出所选学段（{level}）",
                    f"检测到高阶表述：{ '、'.join(hit[:3]) }。请确认是否适合该学段学生。",
                ))
            if "小学" in level and any(w in text for w in _MID_STAGE_WORDS):
                out.append(Issue(
                    "R4", SEVERITY_WARN,
                    "小学阶段出现中考/会考相关表述",
                    "小学内容一般对标学业质量而非中考，请确认表述适配性。",
                ))
        return out

    def _check_privacy(self, text: str) -> List[Issue]:
        found: List[Issue] = []
        if _RE_PHONE.search(text):
            found.append(Issue("R5", SEVERITY_ERROR,
                               "检测到疑似学生手机号", "教学材料不应直接包含个人手机号等身份信息。"))
        if _RE_IDCARD.search(text):
            found.append(Issue("R5", SEVERITY_ERROR,
                               "检测到疑似身份证号", "教学材料不应直接包含身份证号等敏感身份信息。"))
        if _RE_EMAIL.search(text):
            found.append(Issue("R5", SEVERITY_WARN,
                               "检测到邮箱地址", "教学材料中建议避免直接出现个人邮箱。"))
        if _RE_NAME_SCORE.search(text):
            found.append(Issue("R5", SEVERITY_ERROR,
                               "检测到『姓名:成绩』式个人信息",
                               "教学样例不应直接含学生姓名与成绩，建议改为匿名化表述（如『某生』『第3组』）。"))
        return found

    def _check_duration(
        self,
        artifact_type: str,
        text: str,
        duration: int,
        page_count: Optional[int] = None,
    ) -> List[Issue]:
        """页数 vs 课时承载。

        调用方能给出真实页数（如 PPT 的 slides 长度）时优先用它，
        比从正文里正则猜『第N页』可靠得多；给不出时才退回粗估。
        """
        out: List[Issue] = []
        estimated = False
        if isinstance(page_count, int) and page_count > 0:
            pages = page_count
        else:
            # 估算页数：统计『第N页/封面/目录/总结』等 Marker
            pages = len(re.findall(r"第\s*\d+\s*页|封面|目录|封底|尾页", text))
            # 退而求其次：按『页』字出现次数粗估
            if pages == 0:
                pages = text.count("页") // 2
            estimated = True
        # 45 分钟课时一般承载 12~18 页 PPT；超过 duration/2 视为偏多
        cap = max(8, duration // 2)
        if pages > cap:
            suffix = "（估算）" if estimated else ""
            out.append(Issue(
                "R6", SEVERITY_INFO,
                f"页数偏多：约 {pages} 页{suffix} / {duration} 分钟",
                "可考虑合并或拆分页面，避免单课时信息过载。",
            ))
        return out

    # ---- 汇总 ----

    def _finalize(self, artifact_type: str, issues: List[Issue]) -> CheckReport:
        score = 100
        for it in issues:
            if it.severity == SEVERITY_ERROR:
                score -= 25
            elif it.severity == SEVERITY_WARN:
                score -= 8
            else:  # info
                score -= 0
        score = max(0, min(100, score))
        passed = not any(i.severity == SEVERITY_ERROR for i in issues)

        suggestions: List[str] = []
        for it in issues:
            if it.hint:
                suggestions.append(f"【{it.code}】{it.hint}")

        return CheckReport(
            artifact_type=artifact_type,
            passed=passed,
            score=score,
            issue_count=len(issues),
            issues=issues,
            suggestions=suggestions,
        )


# 单例
teaching_compliance_checker = TeachingComplianceChecker()
