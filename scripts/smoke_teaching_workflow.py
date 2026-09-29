"""教学意图 / 教学蓝图 / 工作流 的冒烟测试（纯本地、零模型额度）。

这一批测的是**第二阶段的数据结构与兼容层**，所以重点不是"功能好不好用"，
而是三类很容易悄悄坏掉、且坏了不会报错的契约：

1. **命名不混淆**：`teaching_intent` 与 `intent_service` 的通用对话意图、
   蓝图与既有 `outline`（教案大纲）必须分得清。
2. **宽容解析**：老数据缺字段、脏类型（None / 字符串 / 数字）都不能炸 ——
   台账里躺着几十节旧课，一炸就全打不开。
3. **不存正文**：台账"只存指针不存正文"的约定不能破，超长内容必须被截断。
4. **兼容 DialogueState**：新状态是**追加**的，原有五个成员的值与语义不变。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.teaching_intent import (  # noqa: E402
    LEVELS, TeachingIntent, stage_for_grade,
    normalize_teaching_intent, missing_key_fields, intent_to_prompt_text,
    sync_intent_with_flat,
)
from app.services.teaching_blueprint import (  # noqa: E402
    BlueprintStep, TeachingBlueprint, normalize_blueprint, validate_blueprint,
    blueprint_to_prompt_text, template_blueprint,
)
from app.services.teaching_workflow import (  # noqa: E402
    WorkflowState, Workflow, to_dialogue_state, from_dialogue_state,
    can_transition, normalize_workflow, transition, STAGE_LABELS,
)
from app.services.course_knowledge import (  # noqa: E402
    build_course_context, compose_generation_context, clear_snapshots,
)
from app.services.dialogue_manager import DialogueState  # noqa: E402

PASS: list = []
FAIL: list = []


def check(name: str, cond: bool, extra: str = "") -> None:
    """extra 只在失败时打印 —— 通过时打出来会被误读成告警。"""
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  {extra}" if (extra and not cond) else ""))


print("\n=== 1. 三个新结构与既有近名结构的区分 ===")
# intent_service 的 intent 是"用户想让系统做什么"，本模块是"这节课要教成什么样"
check("教学意图模块不叫 intent_service 那一套",
      "TeachingIntent" in globals() and "teachingIntent" not in dir())
check("学段沿用后端既有取值（不自造口径）",
      "小学" in LEVELS and "初中" in LEVELS and "普通高中" in LEVELS, str(LEVELS))
check("蓝图的字段名与 outline（教案大纲）不重名",
      not any(k.startswith("outline") for k in TeachingBlueprint().__dict__),
      str(list(TeachingBlueprint().__dict__)))

print("\n=== 2. 学段派生 ===")
for grade, want in (("一年级", "小学"), ("六年级", "小学"), ("七年级", "初中"),
                    ("九年级", "初中"), ("高一", "普通高中"), ("高三", "普通高中"),
                    ("", ""), (None, ""), ("三年级半", "")):
    got = stage_for_grade(grade)
    check(f"stage_for_grade({grade!r}) → {want!r}", got == want, f"实得 {got!r}")
# 认得出学段、认不出年级的情况（"高中语文"）
check("直接给 stage='高中' 归一为普通高中",
      stage_for_grade("", "高中") == "普通高中")
check("stage 优先于 grade", stage_for_grade("七年级", "小学") == "小学")

print("\n=== 3. 教学意图：宽容解析（老数据/脏数据都不能炸）===")
for bad in (None, {}, [], "字符串", 123, {"topic": None, "goals": "不是列表"}):
    try:
        it = normalize_teaching_intent(bad)
        ok = isinstance(it, TeachingIntent)
    except Exception as e:  # noqa: BLE001
        ok = False
        it = None
        check(f"脏输入 {bad!r} 不抛异常", False, str(e))
    if ok:
        check(f"脏输入 {type(bad).__name__} 能安全解析", True)

i0 = normalize_teaching_intent({})
check("空输入 → 全部为空（不编造）",
      i0.topic == "" and i0.goals == [] and i0.knowledgePoints == [])
check("空输入 duration 有默认 45", i0.duration == 45)
check("空输入 difficulty 有默认 medium", i0.difficulty == "medium")

base = {"topic": "浮力", "subject": "物理", "grade": "八年级", "duration": 45}
i1 = normalize_teaching_intent({"goals": ["能计算浮力"], "knowledgePoints": ["阿基米德原理"]},
                               base=base)
check("base 的扁平字段被沿用（不另存副本）",
      i1.topic == "浮力" and i1.subject == "物理" and i1.grade == "八年级")
check("stage 自动派生", i1.stage == "初中", i1.stage)
check("goals 被解析", i1.goals == ["能计算浮力"], str(i1.goals))

print("\n=== 4. 教学意图：不编造 + 长度封顶（台账不存正文）===")
check("字符串形式的列表也能解析",
      normalize_teaching_intent({"goals": "目标一；目标二"}).goals == ["目标一", "目标二"])
long_text = "正文" * 5000
i2 = normalize_teaching_intent({"goals": [long_text], "learnerNote": long_text})
check("超长条目被截断（每条 ≤ 200）", len(i2.goals[0]) <= 200, str(len(i2.goals[0])))
check("超长自由文本被截断（≤ 500）", len(i2.learnerNote) <= 500, str(len(i2.learnerNote)))
check("整份意图序列化后体积可控（< 4KB）",
      len(str(i2.to_dict())) < 4096, str(len(str(i2.to_dict()))))
i3 = normalize_teaching_intent({"duration": 999})
check("duration 沿用后端钳制 15–180", i3.duration == 180, str(i3.duration))
check("duration 非法值回落默认", normalize_teaching_intent({"duration": "abc"}).duration == 45)
check("difficulty 非法值回落 medium",
      normalize_teaching_intent({"difficulty": "超难"}).difficulty == "medium")

print("\n=== 5. 教学意图：已识别的不重问 ===")
i4 = normalize_teaching_intent(base)
check("识别到主题学科年级后仍缺目标与知识点",
      missing_key_fields(i4) == ["教学目标", "知识点"], str(missing_key_fields(i4)))
i5 = normalize_teaching_intent({"goals": ["能计算浮力"], "knowledgePoints": ["阿基米德原理"]},
                               base=base)
check("补全后不再有缺失项", missing_key_fields(i5) == [], str(missing_key_fields(i5)))
check("filled 记录了已识别字段", "topic" in i5.filled and "goals" in i5.filled, str(i5.filled))
check("未识别字段不在 filled 里", "methods" not in i5.filled)

print("\n=== 6. 教学意图：给四路的统一文本 ===")
txt = intent_to_prompt_text(i5)
check("含主题", "浮力" in txt)
check("含知识点", "阿基米德原理" in txt)
check("含课时", "45 分钟" in txt)
check("缺失项写明'待教师补充'而不是编造", "待教师补充" in txt)
check("空意图返回空串（不产生噪声）", intent_to_prompt_text(TeachingIntent()) == "")

print("\n=== 7. 教学蓝图：宽容解析 ===")
for bad in (None, {}, [], "字符串", {"stages": "不是列表"}):
    try:
        bp = normalize_blueprint(bad)
        ok = isinstance(bp, TeachingBlueprint)
    except Exception as e:  # noqa: BLE001
        ok = False
        check(f"蓝图脏输入 {bad!r} 不抛异常", False, str(e))
    if ok:
        check(f"蓝图脏输入 {type(bad).__name__} 能安全解析", True)

b0 = normalize_blueprint({})
check("空蓝图 stages 为空", b0.stages == [])
check("空蓝图 status 默认 draft", b0.status == "draft")
check("空蓝图 source 默认 template", b0.source == "template")
check("status 非法值回落 draft", normalize_blueprint({"status": "乱"}).status == "draft")
check("环节数量封顶 12", len(normalize_blueprint(
    {"stages": [{"name": f"s{i}"} for i in range(50)]}).stages) == 12)
check("minutes 非法值回落 0",
      normalize_blueprint({"stages": [{"minutes": "abc"}]}).stages[0].minutes == 0)

print("\n=== 8. 教学蓝图：校验只报告、不阻断 ===")
bp = normalize_blueprint({"stages": [
    {"name": "导入", "minutes": 5},
    {"name": "讲解", "minutes": 40},
]})
w = validate_blueprint(bp, i5)
check("返回的是提示而不是抛异常", isinstance(w, list) and len(w) > 0, str(w))
check("缺练习环节会被提示", any("练习" in x for x in w), str(w))
check("缺小结环节会被提示", any("总结" in x for x in w), str(w))
check("未覆盖知识点会被点名", any("阿基米德原理" in x for x in w), str(w))
check("有瑕疵的蓝图仍然可用（status 不变）", bp.status == "draft")
check("空蓝图也只提示不炸", isinstance(validate_blueprint(b0), list))

print("\n=== 9. 教学蓝图：离线模板兜底（蓝图失败不阻断）===")
tpl = template_blueprint("浮力", 45)
check("模板有五个环节", len(tpl.stages) == 5, str(len(tpl.stages)))
check("模板总时长等于课时", sum(s.minutes for s in tpl.stages) == 45,
      str(sum(s.minutes for s in tpl.stages)))
check("模板 source 标记为 template", tpl.source == "template")
check("模板自带提示（不假装是模型生成）", len(tpl.warnings) > 0)
check("30 分钟的课也能分配", sum(s.minutes for s in template_blueprint("x", 30).stages) == 30)
check("异常课时被钳制", template_blueprint("x", 999).totalMinutes <= 180)

print("\n=== 10. 教学蓝图：四路共用的文本必须含全部关键要素 ===")
bp2 = normalize_blueprint({
    "status": "confirmed",          # 只有教师确认过的蓝图才指导生成
    "stages": [
        {"name": "导入", "minutes": 5, "purpose": "引出问题"},
        {"name": "探究", "minutes": 15, "interaction": "分组实验",
         "knowledgeRefs": ["阿基米德原理"], "isKeyPoint": True, "isHardPoint": True},
        {"name": "练习", "minutes": 15, "output": "完成三道题"},
        {"name": "小结", "minutes": 10},
    ]})
btxt = blueprint_to_prompt_text(bp2)
for kw, label in (("阿基米德原理", "知识点"), ("分组实验", "活动"),
                  ("15 分钟", "时间安排"), ("重点", "重点标记"), ("难点", "难点标记")):
    check(f"蓝图文本含{label}", kw in btxt, f"缺少 {kw!r}")
check("空蓝图返回空串", blueprint_to_prompt_text(normalize_blueprint({})) == "")

print("\n=== 10b. 未确认/跳过的蓝图不得指导生成 ===")
# 此前只要蓝图有环节就拼进 prompt，还写着"已确认的环节安排，务必按此生成" ——
# 而 draft 是模型刚生成、教师还没表态，skipped 是教师点了"直接生成"。
# 把这两种也注入，等于让教师没认可过的安排去支配四路产物。
same_stages = {"stages": [{"name": "探究", "minutes": 15,
                           "knowledgeRefs": ["阿基米德原理"]}]}
for st in ("draft", "skipped"):
    t = blueprint_to_prompt_text(normalize_blueprint({**same_stages, "status": st}))
    check(f"status={st} 的蓝图不注入 prompt", t == "", f"实际注入了 {len(t)} 字")
t_confirmed = blueprint_to_prompt_text(
    normalize_blueprint({**same_stages, "status": "confirmed"}))
check("status=confirmed 的蓝图正常注入", "阿基米德原理" in t_confirmed)
check("注入文本如实标注'已确认'", "已确认" in t_confirmed)

_, _, meta_draft = compose_generation_context(
    topic="浮力", kind="lesson_plan", use_snapshot=False,
    blueprint={**same_stages, "status": "draft"})
check("meta 如实报告蓝图未用上", meta_draft["blueprint_used"] is False)
check("meta 保留蓝图状态供前端显示", meta_draft["blueprint_status"] == "draft")
_, _, meta_ok = compose_generation_context(
    topic="浮力", kind="lesson_plan", use_snapshot=False,
    blueprint={**same_stages, "status": "confirmed"})
check("meta 如实报告蓝图已用上", meta_ok["blueprint_used"] is True)

print("\n=== 10c. 台账单一真值：意图与扁平字段不能各说一套 ===")
# 事故形态：先保存了带主题的意图，之后教师只改扁平主题 ——
# 若不同步，同一节课会有两个主题，后续生成依据哪个是不确定的，且不报错。
it_a, patch_a = sync_intent_with_flat(
    {"topic": "浮力", "subject": "物理", "grade": "八年级", "goals": ["能计算浮力"]},
    {"topic": "压强", "subject": "物理", "grade": "八年级", "duration": 45,
     "difficulty": "medium"})
check("扁平字段是真值：改主题后意图跟着变", it_a["topic"] == "压强", it_a["topic"])
check("意图专属字段不受影响", it_a["goals"] == ["能计算浮力"], str(it_a["goals"]))
check("无冲突时不产生回写", patch_a == {}, str(patch_a))

it_b, patch_b = sync_intent_with_flat(
    {"topic": "浮力", "subject": "物理", "grade": "八年级", "duration": 45},
    {"topic": "", "subject": "", "grade": "", "duration": None, "difficulty": ""})
check("扁平字段为空时采用意图里的值", it_b["topic"] == "浮力")
check("回写补丁供台账补齐扁平字段", patch_b.get("topic") == "浮力", str(patch_b))
check("stage 由 grade 派生", it_b["stage"] == "初中", it_b["stage"])
check("脏数据不抛异常",
      sync_intent_with_flat({"duration": "abc"}, {"topic": "x", "duration": "约45分钟"})[0]
      ["duration"] == 45)

print("\n=== 10d. 四路共用同一份知识快照（引用必须一致）===")
class _FakeHit:
    def __init__(self, src, path="p1"):
        self.text = src + " 正文"
        self.raw_text = src + " 正文"
        self.score = 0.9
        self.source = src
        self.heading_path = path
        self.metadata = {}

class _FakeResult:
    def __init__(self, hits):
        self.hits = hits
        self.refused = False

class _FakeRetriever:
    """每检索一次就换一批资料 —— 模拟真实检索的顺序/批次差异。"""
    def __init__(self):
        self.calls = 0
    def retrieve(self, query, top_k=4, filters=None, enable_rerank=True):
        self.calls += 1
        return _FakeResult([_FakeHit(f"资料{self.calls}")])

clear_snapshots()
r = _FakeRetriever()
k_plan = build_course_context(topic="浮力", subject="物理", grade="八年级",
                              kind="lesson_plan", retriever=r, lesson_id="L1")
k_ppt = build_course_context(topic="浮力", subject="物理", grade="八年级",
                             kind="ppt", retriever=r, lesson_id="L1")
k_anim = build_course_context(topic="浮力", subject="物理", grade="八年级",
                              kind="animation", retriever=r, lesson_id="L1")
# 首次构建本身要发两路查询（学科知识 + 教学策略），之后的产物必须命中快照
first_calls = r.calls
k_game = build_course_context(topic="浮力", subject="物理", grade="八年级",
                              kind="game", retriever=r, lesson_id="L1")
check("后续产物不再重复检索（命中快照）", r.calls == first_calls,
      f"首次 {first_calls} 次，之后变成 {r.calls} 次")
check("四路引用同一批资料",
      [c["source"] for c in k_game.citations] == [c["source"] for c in k_plan.citations])
check("教案与 PPT 引用同一批资料",
      [c["source"] for c in k_plan.citations] == [c["source"] for c in k_ppt.citations])
check("动画也引用同一批资料",
      [c["source"] for c in k_plan.citations] == [c["source"] for c in k_anim.citations])
check("换成别的课后重新检索",
      build_course_context(topic="浮力", subject="物理", grade="八年级",
                           kind="ppt", retriever=r, lesson_id="L2").citations
      != k_plan.citations)
check("use_snapshot=False 时按原样各检索一遍",
      build_course_context(topic="浮力", kind="ppt", retriever=r,
                           use_snapshot=False).citations != [])
clear_snapshots()

print("\n=== 11. 工作流：与 DialogueState 的兼容映射（只追加不替换）===")
# 原有五个成员的值与语义必须一字不变
for name, val in (("INITIAL", "initial"), ("CLARIFYING", "clarifying"),
                  ("CONFIRMING", "confirming"), ("EXECUTING", "executing"),
                  ("COMPLETED", "completed")):
    check(f"DialogueState.{name} 仍为 {val!r}",
          getattr(DialogueState, name).value == val)
check("新增 REVIEWING（追加，非替换）", DialogueState.REVIEWING.value == "reviewing")
check("新增 FAILED（追加，非替换）", DialogueState.FAILED.value == "failed")

for wf_state, d_state in (
        ("collecting", "initial"), ("clarifying", "clarifying"),
        ("intent_ready", "confirming"), ("blueprint_ready", "confirming"),
        ("awaiting_confirmation", "confirming"), ("generating", "executing"),
        ("reviewing", "reviewing"), ("completed", "completed"),
        ("failed", "failed")):
    got = to_dialogue_state(wf_state)
    check(f"{wf_state} → {d_state}", got == d_state, f"实得 {got}")
    check(f"映射结果 {d_state} 是 DialogueState 的真实成员",
          d_state in {s.value for s in DialogueState})

check("未知工作流状态回落 initial（不抛异常）", to_dialogue_state("乱状态") == "initial")
check("未知对话状态回落 collecting（不抛异常）",
      from_dialogue_state("乱状态") == "collecting")
for d in ("initial", "clarifying", "confirming", "executing", "reviewing",
          "completed", "failed"):
    back = to_dialogue_state(from_dialogue_state(d))
    check(f"往返映射一致 {d}", back == d, f"实得 {back}")

print("\n=== 12. 工作流：状态迁移 ===")
check("collecting → clarifying 允许", can_transition("collecting", "clarifying"))
check("blueprint_ready → generating 允许（跳过蓝图直接生成）",
      can_transition("blueprint_ready", "generating"))
check("generating → reviewing 允许", can_transition("generating", "reviewing"))
check("generating → failed 允许", can_transition("generating", "failed"))
check("failed → generating 允许（可恢复）", can_transition("failed", "generating"))
check("failed → collecting 允许（改需求重来）", can_transition("failed", "collecting"))
check("completed → generating 允许（再生成一版）", can_transition("completed", "generating"))
check("未知状态一律放行（老数据不被卡死）", can_transition("乱", "也乱"))

w1 = normalize_workflow({"state": "generating"})
check("非法迁移被忽略且不抛异常",
      transition(w1, "collecting").state == "generating")
w2 = normalize_workflow({"state": "blueprint_ready"})
w2 = transition(w2, "generating", activeKinds=["lesson_plan"])
check("合法迁移生效", w2.state == "generating")
check("迁移时 dialogueState 同步（不漂移）",
      w2.dialogueState == "executing", w2.dialogueState)

print("\n=== 13. 工作流：刷新恢复 ===")
w3 = normalize_workflow({"state": "generating"}, restore=True)
check("generating 恢复成 failed", w3.state == "failed", w3.state)
check("恢复后标记为可恢复", w3.lastError.get("recoverable") is True)
w4 = normalize_workflow({"state": "reviewing"}, restore=True)
check("reviewing 恢复成 failed", w4.state == "failed")
w5 = normalize_workflow({"state": "completed"}, restore=True)
check("completed 不受恢复影响", w5.state == "completed")

print("\n=== 14. 工作流：宽容解析与默认值 ===")
for bad in (None, {}, [], "字符串", 123):
    try:
        w = normalize_workflow(bad)
        ok = isinstance(w, Workflow)
    except Exception as e:  # noqa: BLE001
        ok = False
        check(f"工作流脏输入 {bad!r} 不抛异常", False, str(e))
    if ok:
        check(f"工作流脏输入 {type(bad).__name__} 能安全解析", True)
w6 = normalize_workflow({})
check("默认状态是 collecting", w6.state == "collecting")
check("默认 dialogueState 是 initial", w6.dialogueState == "initial")
check("非法状态回落 collecting", normalize_workflow({"state": "乱"}).state == "collecting")
check("每个状态都有中文名（教师看得懂）",
      all(s in STAGE_LABELS for s in WorkflowState.ALL))
check("progress 非字典时被清空",
      normalize_workflow({"progress": "乱"}).progress == {})
check("lastError 非字典时被清空",
      normalize_workflow({"lastError": "乱"}).lastError == {})
check("工作流序列化后体积很小（< 2KB）",
      len(str(normalize_workflow({"state": "generating"}).to_dict())) < 2048)

print("\n=== 15. 台账字段归一化：只存结构化，不存正文 ===")
from app.api.lesson_tasks import (  # noqa: E402
    _normalize_teaching_intent_field, _normalize_blueprint_field,
    _normalize_workflow_field,
)

body_intent = {"topic": "浮力", "goals": ["能计算"], "learnerNote": "正文" * 5000}
n_intent = _normalize_teaching_intent_field(body_intent)
check("意图字段被归一化（含 stage）", "stage" in n_intent and "goals" in n_intent)
check("意图字段不含超长正文", len(str(n_intent)) < 4096, str(len(str(n_intent))))

# 教学意图是现有课程字段的**视图**：不传 base 时 grade 不在里面，
# stage 就派生不出来 —— 台账里会存下一份"学科年级齐全、学段为空"的残缺意图。
n_view = _normalize_teaching_intent_field(
    {"goals": ["能计算浮力"]},
    base={"topic": "浮力", "subject": "物理", "grade": "八年级", "duration": 45},
)
check("传了 base 后 topic/grade 被沿用", n_view["topic"] == "浮力"
      and n_view["grade"] == "八年级", str({k: n_view[k] for k in ("topic", "grade")}))
check("传了 base 后 stage 能派生出来", n_view["stage"] == "初中", str(n_view["stage"]))
n_nobase = _normalize_teaching_intent_field({"goals": ["能计算浮力"]})
check("不传 base 时 stage 为空（这正是要避免的）", n_nobase["stage"] == "",
      str(n_nobase["stage"]))

huge_blueprint = {"stages": [{"name": "导入", "teacherActivity": "正文" * 10000}]}
n_bp = _normalize_blueprint_field(huge_blueprint)
check("蓝图字段被截断（不含正文）", len(str(n_bp)) < 4096, str(len(str(n_bp))))
check("蓝图字段保留结构", len(n_bp.get("stages") or []) == 1)

n_wf = _normalize_workflow_field({"state": "generating"})
check("工作流字段被归一化", n_wf["state"] == "generating")
check("工作流字段不含正文", len(str(n_wf)) < 2048)

for fn, bad in ((_normalize_teaching_intent_field, "字符串"),
                (_normalize_blueprint_field, 123),
                (_normalize_workflow_field, [])):
    try:
        fn(bad)
        check(f"{fn.__name__} 脏输入不抛异常", True)
    except Exception as e:  # noqa: BLE001
        check(f"{fn.__name__} 脏输入不抛异常", False, str(e))

print("\n=== 16. 蓝图模型生成：失败必须回落，绝不阻断 ===")
from app.services.teaching_blueprint import (  # noqa: E402
    generate_blueprint, _extract_json, _rescale_minutes,
)


class _DeadModel:
    """模拟 llm_service 不可用。"""
    def chat(self, *a, **kw):
        raise RuntimeError("模型不可用")


class _JunkModel:
    """模拟模型返回一堆废话，没有 JSON。"""
    def chat(self, *a, **kw):
        return "好的，我来帮你设计，但是我不太确定，你可以再说说你的想法吗？"

    def __bool__(self):
        return True


class _EmptyStagesModel:
    def chat(self, *a, **kw):
        return '{"summary":"有思路","stages":[]}'


class _BadTimeModel:
    """模型把时长加错了（总 90 分钟，但课时 45）。"""
    def chat(self, *a, **kw):
        return '{"summary":"s","stages":[{"name":"导入","minutes":10},{"name":"练习","minutes":80}]}'


_it = normalize_teaching_intent(
    {"topic": "浮力", "subject": "物理", "grade": "八年级", "duration": 45})

# 用假的 llm_service 顶替，避免测试真的去调模型（零额度、可离线）
import app.services.llm_service as _llm_mod  # noqa: E402

_orig = getattr(_llm_mod, "llm_service", None)
for name, fake in (("模型抛异常", _DeadModel()), ("返回非 JSON", _JunkModel()),
                   ("环节为空", _EmptyStagesModel())):
    _llm_mod.llm_service = fake
    try:
        bp = generate_blueprint(_it)
        ok = bool(bp.stages) and bp.source == "template" and bool(bp.error)
    except Exception as e:  # noqa: BLE001
        ok = False
        check(f"{name} 时不抛异常", False, str(e))
    if ok:
        check(f"{name} → 回落模板且写明原因", True)
        check(f"{name} → 蓝图仍然可用", len(bp.stages) >= 5, str(len(bp.stages)))

_llm_mod.llm_service = _BadTimeModel()
bpt = generate_blueprint(_it)
check("时长加错时按比例重分配",
      abs(sum(s.minutes for s in bpt.stages) - 45) <= 2,
      str(sum(s.minutes for s in bpt.stages)))
check("重分配后环节数不变", len(bpt.stages) == 2, str(len(bpt.stages)))

if _orig is not None:
    _llm_mod.llm_service = _orig

check("JSON 提取：能剥掉 markdown 代码块",
      (_extract_json('```json\n{"a":1}\n```') or {}).get("a") == 1)
check("JSON 提取：外面裹话也能抠出来",
      (_extract_json('好的：{"a":1} 就这样') or {}).get("a") == 1)
check("JSON 提取：纯废话返回 None", _extract_json("完全没有 JSON") is None)
check("JSON 提取：空串返回 None", _extract_json("") is None)

print("\n=== 17. 知识库范围（system / personal / both / none）===")
from app.services.course_knowledge import (  # noqa: E402
    build_course_context, scope_filters, KNOWLEDGE_SCOPES, _SCOPE_NAMES,
)

check("四种范围都定义了", set(KNOWLEDGE_SCOPES) == {"system", "personal", "both", "none"})
check("system → 过滤 origin=seed（复用已有的来源标记）",
      scope_filters("system") == {"origin": "seed"})
check("personal → 过滤 origin=upload", scope_filters("personal") == {"origin": "upload"})
check("both → 不过滤", scope_filters("both") is None)
check("未知范围按 both 处理（不静默变窄）", scope_filters("乱") is None)
check("每种范围都有中文名（教师看得懂）", all(s in _SCOPE_NAMES for s in KNOWLEDGE_SCOPES))


class _SeedOnlyRetriever:
    """只含系统库片段的假检索器。"""

    class _H:
        def __init__(self, src, text):
            self.chunk_id = f"c_{src}_{text[:8]}"
            self.text = self.raw_text = text
            self.source = src
            self.heading_path = "节"
            self.score = 0.9

    class _R:
        def __init__(self, hits):
            self.refused = False
            self.hits = hits

    def retrieve(self, query, top_k=5, filters=None, enable_rerank=True, **kw):
        pool = [
            self._H("22_初中物理", "系统库片段：阿基米德原理"),
            self._H("我的课件.pdf", "个人库片段：班级学情"),
        ]
        if filters:
            pool = [h for h in pool
                    if all(h.__dict__.get(k) == v for k, v in filters.items()
                           if k in ("source",))]
            # origin 不在 hit 上，用约定：系统库来源是 knowledge_base 的 stem
            if filters.get("origin") == "seed":
                pool = [h for h in pool if h.source.startswith(("1", "2", "3"))]
            elif filters.get("origin") == "upload":
                pool = [h for h in pool if not h.source[:1].isdigit()]
        return self._R(pool[:top_k])


r = _SeedOnlyRetriever()
k_sys = build_course_context(topic="浮力", subject="物理", scope="system", retriever=r)
k_per = build_course_context(topic="浮力", subject="物理", scope="personal", retriever=r)
k_none = build_course_context(topic="浮力", subject="物理", scope="none", retriever=r)
check("system 只拿系统库", all(c["source"][:1].isdigit() for c in k_sys.citations),
      str([c["source"] for c in k_sys.citations]))
check("personal 只拿个人库", all(not c["source"][:1].isdigit()
                             for c in k_per.citations),
      str([c["source"] for c in k_per.citations]))
check("none 时完全不检索", k_none.empty and not k_none.used)
check("none 的原因写明是教师选择", "不使用知识库" in k_none.reason, k_none.reason)
check("used 标记与是否有片段一致", k_sys.used == bool(k_sys.citations))

class _RefusedRetriever:
    """模拟知识库判定为无关（拒答）。"""

    class _R:
        refused = True
        hits = []

    def retrieve(self, *a, **kw):
        return self._R()


k_refused = build_course_context(topic="浮力", scope="both", retriever=_RefusedRetriever())
check("拒答时不伪造引用", k_refused.empty and not k_refused.citations)
check("拒答时必须写明未检索到", "未能检索到" in k_refused.reason, k_refused.reason)
check("未检索到时提示教师核验", "核验" in k_refused.reason, k_refused.reason)
check("范围会写进给模型的文本里", "范围：" in k_sys.text, k_sys.text[:40])

print("\n=== 18. 蓝图接口：恒不阻断 ===")
from app.api.teaching import router as _teaching_router  # noqa: E402

paths = {getattr(rt, "path", "") for rt in _teaching_router.routes}
check("接口 /teaching/blueprint 存在", "/teaching/blueprint" in paths, str(sorted(paths)))
check("接口 /teaching/blueprint/validate 存在",
      "/teaching/blueprint/validate" in paths)
src_api = (ROOT / "backend" / "app" / "api" / "teaching.py").read_text(encoding="utf-8")
check("接口里没有 success=False 的分支（失败不阻断）",
      '"success": False' not in src_api and "'success': False" not in src_api)
check("接口走 run_in_threadpool（不堵事件循环）",
      "run_in_threadpool" in src_api)
check("接口不直连模型供应商",
      not any(k in src_api for k in ("openai", "dashscope", "ChatOpenAI")))

print("\n=== 19. 静态：不引新框架、不绕过 llm_service ===")
for mod in ("app/services/teaching_intent.py",
            "app/services/teaching_blueprint.py",
            "app/services/teaching_workflow.py"):
    src = (ROOT / "backend" / mod).read_text(encoding="utf-8")
    check(f"{Path(mod).name} 不引入 LangChain/LangGraph",
          not any(k in src for k in ("langchain", "langgraph", "openai", "dashscope")))
    forbidden = ("openai", "dashscope", "zhipuai", "ChatOpenAI", "chat_completions")
    check(f"{Path(mod).name} 不直连模型供应商", not any(k in src for k in forbidden))
    if mod.endswith("teaching_blueprint.py"):
        # 允许调模型，但必须是 llm_service（出校插桩在它里面），且是函数内惰性导入
        check("蓝图走 llm_service（插桩在它里面）", "from .llm_service import llm_service" in src)
        check("蓝图不在模块顶层导入模型服务（避免启动时拖慢/连带崩溃）",
              not src.lstrip().startswith("from .llm_service") and
              src.count("from .llm_service import llm_service") == 1)
    else:
        check(f"{Path(mod).name} 不碰模型（本步无模型调用）", "llm_service" not in src)
    check(f"{Path(mod).name} 不碰台账与版本正文",
          "artifact_versions" not in src and "lesson_task_store" not in src)

print(f"\n通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
if FAIL:
    print("失败项：" + "、".join(FAIL))
    sys.exit(1)
