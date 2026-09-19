"""工作台对话的"教学语境 + 身份"组装。

存在的理由：工作台原来的对话只会**路由** —— 把教师的一句话判定成
生成 / 修改 / 追问，唯独不会**回答问题**。教师问「什么是三角函数」，
系统回「请问您想了解什么主题的知识？」（把提问当成需求收集），
再问就只剩一句「你直接说要生成什么」。那不是智能体，是套了层壳的菜单。

这里补上缺的那一半：把"这节课的语境"+"教学智能体的身份与行为准则"
组装成 system 指令，交给真正的模型去回答。

为什么放 system 而不是拼进用户消息：
  1. 语境是**长期背景**，每一轮都在。拼进用户消息会让模型以为
     "教师刚刚说了这么一长串课程信息"；
  2. 出校守卫（`llm_client` 里的 `_guard`）按**整条 messages** 处理，
     system 同样受管，不会绕过脱敏与阻断；
  3. prompt 组装属于服务端职责。放到前端会散落到多个组件里，
     改一次要翻好几处，也没法加测试。
"""
from typing import Any, Dict, List

# 成品类型 → 中文名。与前端 store 的 artifact id 对齐，
# 不一致时按 id 原样显示，绝不猜（猜错会让教师以为生成过）。
_ARTIFACT_NAMES: Dict[str, str] = {
    "lesson_plan": "教案",
    "ppt": "PPT 课件",
    "animation": "动画演示",
    "game": "互动游戏",
}

# 成品状态 → 人话。只认这几种，其余不写进语境（宁可不提，也不虚报）。
_ARTIFACT_STATUS: Dict[str, str] = {
    "done": "已完成",
    "running": "正在生成",
    "failed": "生成失败",
}

_DIFFICULTY_NAMES = {"easy": "入门级", "medium": "中等难度", "hard": "进阶深入"}


def _clean(value: Any, limit: int = 200) -> str:
    """单行化 + 截断。教师手填的内容可能带换行，塞进指令里会破坏排版。"""
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    return text[:limit]


def describe_artifacts(artifacts: Any) -> str:
    """把成品状态说成一句人话；没有成品时明确说"还没有"。

    为什么不让模型自己推断"生成过没有"：
    它没有这个信息，只能猜。猜"已经生成好了"比不说更糟 ——
    教师会以为成果在，实际去点下载才发现是空的。

    认不出的类型与状态一律**丢掉**（不是原样透传）：编出来的名字会让模型
    围绕一个不存在的成果展开，而"少提一条"最多是少说一句话。
    """
    if not isinstance(artifacts, dict) or not artifacts:
        return "这节课目前还没有生成任何成果。"

    parts: List[str] = []
    for key, raw_status in artifacts.items():
        name = _ARTIFACT_NAMES.get(str(key))
        human = _ARTIFACT_STATUS.get(str(raw_status or "").strip().lower())
        if not name or not human:
            continue
        parts.append(f"{name}（{human}）")

    if not parts:
        return "这节课目前还没有生成任何成果。"
    return "这节课已生成的成果：" + "、".join(parts) + "。"


def build_lesson_context(lesson: Any) -> str:
    """这节课的语境。教师还没填主题时**如实说明**，不要编一个。

    注意这里的分支不是"整段有 / 整段无"：学科和年级是下拉框选的，
    往往先于主题存在。按最粗的那一刀切会让"选了学科还没想好主题"这种
    最常见的中途状态，被模型当成"已经有一节课了"，接着开始编主题相关内容。
    """
    if not isinstance(lesson, dict):
        lesson = {}

    topic = _clean(lesson.get("topic"))
    subject = _clean(lesson.get("subject"), 40)
    grade = _clean(lesson.get("grade"), 40)
    duration = lesson.get("duration")
    difficulty = _clean(lesson.get("difficulty"), 40)
    key_points = _clean(lesson.get("keyPoints") or lesson.get("key_points"), 400)

    lines = ["【当前这节课】"]
    if topic:
        lines.append(f"- 教学主题：{topic}")
    else:
        lines.append(
            "- 教师还没有填写教学主题。不要假设他在准备哪一节课，"
            '也不要说"根据你之前说的"。'
        )
    if subject:
        lines.append(f"- 学科：{subject}")
    if grade:
        lines.append(f"- 年级：{grade}")
    try:
        minutes = int(duration)
    except (TypeError, ValueError):
        minutes = 0
    if minutes > 0:
        lines.append(f"- 课时：{minutes} 分钟")
    if difficulty:
        lines.append(f"- 难度定位：{_DIFFICULTY_NAMES.get(difficulty, difficulty)}")
    if key_points:
        lines.append(f"- 教师补充要求 / 教学要点：{key_points}")
    lines.append(f"- {describe_artifacts(lesson.get('artifacts'))}")
    return "\n".join(lines)


_PROMPT_TEMPLATE = """你是 EduForge 的教学智能体，身份是一位带过多届毕业班、常年做教研的资深教师。

{context}

【你要怎么回答】
1. 教师问知识、概念、原理、教法、学生问题 —— **直接回答**。不要反问他"你想了解什么主题"，
   也不要说"请提供更多信息"。他已经在提问了，提问本身就是信息。
2. 贴住上面这个学段和学科：用这个年级的学生能听懂的说法、能见到的例子。
   没有把握时给出通用解释并说明适用范围，不要硬套。
3. 讲知识点时顺带说"怎么讲"：一个切入角度、学生最常见的误区、一个能现场用的例子或追问。
   这是教研员和搜索引擎的区别。
4. 确实缺少关键信息（比如不知道年级）时才追问，一次最多问**一个**最关键的问题。
5. 绝不能声称你已经生成了教案 / PPT / 动画 / 游戏。生成由工作台的按钮执行，
   你只负责解答与建议。如果教师的话本质上是"想做点什么"，先正面回答他的问题，
   再告诉他点哪个按钮；信息够就直接说"可以点「生成教案」"。
6. 输出用简体中文。短段落 + 要点列表，不要用"好的，我完全理解了您的需求"这类套话开头，
   直接从答案本身开始。
7. 涉及实验、器材、危险操作时，补一句安全提示。

{knowledge}
"""


def build_lesson_system_prompt(lesson: Any, knowledge: str = "") -> str:
    """组装工作台对话的 system 指令。

    知识库片段走 system 而不是拼进用户消息，理由与课程语境相同：
    检索片段是**参考资料**，不是"教师刚刚说的话"。既有通用对话
    （`/api/chat/*`）把 `[知识库参考]` 拼进 message 是因为那条链路没有
    system 通道；工作台这条有，就用对的那条。**同一件事只留一个位置**，
    两边都放会让片段出现两次、白烧 token 还干扰模型。

    `knowledge` 为空时明确写"没有检索到"，否则模型容易把"没给资料"
    理解成"资料里查不到这条内容"从而不敢回答。
    """
    context = build_lesson_context(lesson)
    kb = (knowledge or "").strip()
    knowledge_block = (
        f"【教师知识库中的相关资料】\n{kb}\n"
        "把这些资料当作优先依据；资料没覆盖到的部分，用你自己的知识回答并说明是通用经验。"
        if kb
        else "【教师知识库中的相关资料】\n本次没有检索到相关资料，直接依据你的专业知识回答。"
    )
    return _PROMPT_TEMPLATE.format(context=context, knowledge=knowledge_block)
