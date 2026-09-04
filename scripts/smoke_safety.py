"""合规模块（app/safety）冒烟测试。

不依赖 TestClient —— 本项目 starlette 0.35 与 httpx 0.28 不兼容
（TestClient 会给 httpx.Client 传已废弃的 app= 参数）。与其为了跑测试升级
运行时依赖，这里直接调用端点函数；对唯一有风险的假设（contextvar 槽位能否
跨 task 回传给中间件）单独构造最小验证。

覆盖：
  1. 本地定级是否准确（含"古诗不该误报"这类反例）
  2. 三种策略模式下的路由决策矩阵
  3. 接口函数 status / scan 的返回结构
  4. contextvar 槽位跨 task 回传（响应头机制的前提）
  5. 脱敏是否保留教学语义
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

os.environ.setdefault("EDUFORGE_SAFETY_MODE", "warn")

from app.api.safety import LEVEL_LABELS, ScanRequest, safety_scan, safety_status  # noqa: E402
from app.core.errors import DataEgressBlockedError  # noqa: E402
from app.core.llm_gateway import get_data_flow, new_data_flow_slot, set_data_flow  # noqa: E402
from app.safety import (  # noqa: E402
    SAFETY_MODES,
    classify,
    decide,
    get_safety_mode,
    is_private_endpoint,
    redact,
)

PASS: list = []
FAIL: list = []


def check(name: str, cond: bool, extra: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  {extra}" if extra else ""))


def set_mode(m: str) -> None:
    os.environ["EDUFORGE_SAFETY_MODE"] = m


# 公网厂商地址（模拟默认配置）
CLOUD = "https://dashscope.aliyuncs.com/compatible-mode/v1"
# 校内推理服务地址（私有网段示例，勿写真实内网地址）
CAMPUS = "http://192.168.1.100:11434/v1"


def test_classify() -> None:
    print("\n== 1. 本地定级（classify）==")
    cases = [
        ("空输入", "", "L1"),
        ("普通课题", "请为初中物理《浮力》设计一节课教案", "L2"),
        ("含手机号", "联系家长王先生 13812345678 沟通学生情况", "L3"),
        ("含邮箱", "把反馈发到 zhangsan@example.com", "L3"),
        ("成绩名单", "本次月考成绩：张三 85 李四 92 王五 78，掌握率 42%", "L4"),
        ("学号", "学号：20230101001 的同学请补交作业", "L3"),
        ("古诗不应误报", "请讲解李白的《静夜思》：床前明月光，疑是地上霜", "L2"),
        ("普通数字不应误报", "本节课共 45 分钟，分为 3 个环节", "L2"),
    ]
    for name, text, want in cases:
        clf = classify(text)
        got = clf.level
        detail = f"(实际 {got}"
        if clf.findings:
            detail += "，" + "、".join(f"{f.label}×{f.count}" for f in clf.findings)
        detail += ")"
        check(f"{name} -> {want}", got == want, detail)


def test_policy_matrix() -> None:
    print("\n== 2. 路由决策矩阵 ==")
    sensitive = "本次月考成绩：张三 85 李四 92 王五 78，掌握率 42%"
    plain = "请为《浮力》设计一节课教案"

    for mode in SAFETY_MODES:
        set_mode(mode)
        d = decide(CLOUD, classify(sensitive), protocol="openai")
        check(f"mode={mode} 敏感内容发公网 -> {d.action}", True,
              f"(allowed={d.allowed})")
        if mode == "enforce":
            check(f"mode={mode} 应阻断", (not d.allowed) and d.action == "block")
        else:
            check(f"mode={mode} 应放行", d.allowed)

        d2 = decide(CLOUD, classify(plain), protocol="openai")
        check(f"mode={mode} 普通内容发公网 -> pass", d2.allowed and d2.action == "pass")

        d3 = decide(CAMPUS, classify(sensitive), protocol="local")
        check(f"mode={mode} 敏感内容发校内 -> pass 且归因 L4",
              d3.allowed and d3.action == "pass" and d3.level == "L4"
              and d3.egress is False)

    set_mode("warn")


def test_sanitize_mode() -> None:
    """sanitize：脱敏后上云；但试题类必须退化为阻断。"""
    print("\n== 2b. sanitize 模式（脱敏后上云）==")
    set_mode("sanitize")

    # 可脱敏：姓名/手机号
    d = decide(CLOUD, classify("本次月考成绩：张三 85 李四 92 王五 78，掌握率 42%"),
               protocol="openai")
    check("成绩名单 -> redact 且放行",
          d.action == "redact" and d.allowed and d.redacted,
          f"(action={d.action})")
    check("理由说明保留教学语义", "教学语义" in d.reason)

    # 不可脱敏：整段试题
    exam = ("1. 下列关于浮力的说法正确的是（ ）\nA. 浮力方向总是竖直向上\n"
            "B. 浮力大小与深度无关\n"
            "2. 一个物体重 10N，浸没在水中弹簧测力计示数为 6N\n"
            "A. 浮力为 4N\nB. 浮力为 6N\n"
            "3. 下列说法正确的是（ ）\nA. 密度大于水的物体一定下沉\nB. 以上都不对\n"
            "4. 计算题：求该物体受到的浮力\nA. 4N\nB. 10N")
    clf = classify(exam)
    check("整段试题被识别", any(f.kind == "exam_paper" for f in clf.findings),
          f"(定级 {clf.level})")
    d2 = decide(CLOUD, clf, protocol="openai")
    check("sanitize 下试题退化为阻断",
          d2.action == "block" and not d2.allowed,
          f"(action={d2.action})")
    check("理由说明题面无法脱敏", "题面" in d2.reason)

    set_mode("warn")


def test_call_paths_guarded() -> None:
    """回归防护：四条 LLM 调用链路的收口点都必须插桩。

    本项目历史上有 4 条彼此独立的 LLM 调用路径，只在网关上装检查会让
    教案/PPT/动画/游戏生成完全裸奔 —— 而那恰恰是最容易粘贴学生名单的地方。
    这里用源码特征做静态校验，防止以后新增链路时漏掉。
    """
    print("\n== 2c. 调用链路插桩完整性 ==")
    backend = ROOT / "backend" / "app"

    def src(rel: str) -> str:
        return (backend / rel).read_text(encoding="utf-8")

    gateway = src("core/llm_gateway.py")
    check("网关 llm_chat 有数据流向判定", "_evaluate_data_flow(" in gateway)
    check("网关 llm_stream 也有判定（不只 llm_chat）",
          gateway.count("_evaluate_data_flow(") >= 2,
          f"(出现 {gateway.count('_evaluate_data_flow(')} 次)")

    client = src("llm_client.py")
    check("llm_client 流式已插桩", "_guard(messages, base_url, provider)" in client)
    check("llm_client 非流式已插桩",
          client.count("_guard(messages, base_url, provider)") >= 2)
    check("llm_client 非流式抛 403",
          "raise DataEgressBlockedError" in client)

    svc = src("services/llm/service.py")
    check("services/llm 非流式已插桩", svc.count("_guard(") >= 3)
    check("services/llm 流式已插桩", "yield _guard_notice(_flow)" in svc)
    check("合规阻断不被包成 LLMUnavailableError",
          "except DataEgressBlockedError:" in svc)


def test_private_endpoint() -> None:
    print("\n== 3. 出校判定（is_private_endpoint）==")
    cases = [
        ("http://192.168.1.100:11434/v1", True),
        ("http://localhost:11434/v1", True),
        ("http://127.0.0.1:8000/v1", True),
        ("http://192.168.1.50:8000/v1", True),
        ("https://dashscope.aliyuncs.com/compatible-mode/v1", False),
        ("https://api.openai.com/v1", False),
        ("http://10.2.3.4:11434", True),
    ]
    for url, want in cases:
        got = is_private_endpoint(url)
        check(f"{url} -> private={want}", got == want, f"(实际 {got})")
    check("空地址 -> private=True", is_private_endpoint("") is True)


def test_api_functions() -> None:
    print("\n== 4. 接口函数 ==")
    st = safety_status()
    check("status 返回 success", st.get("success") is True)
    check("status 含 mode", st.get("mode") in SAFETY_MODES, f"({st.get('mode')})")
    check("status 含 target.private", isinstance(st.get("target", {}).get("private"), bool))
    check("status 含级别说明", set(LEVEL_LABELS) >= {"L1", "L2", "L3", "L4", "L5"})
    print(f"      target = {st.get('target')}")

    r = safety_scan(ScanRequest(
        text="本次月考成绩：张三 85 李四 92 王五 78", preview_redact=True,
    ))
    check("scan 定级 L4", r.get("level") == "L4", f"(实际 {r.get('level')})")
    check("scan 返回 findings", len(r.get("findings") or []) > 0)
    check("scan 给出决策理由", bool(r.get("reason")))
    check("scan 脱敏预览生效", "学生A" in (r.get("redacted_text") or ""),
          f"(替换 {r.get('redacted_count')} 处)")
    print("      原文: 本次月考成绩：张三 85 李四 92 王五 78")
    print(f"      脱敏: {r.get('redacted_text')}")

    r2 = safety_scan(ScanRequest(text="请设计《浮力》一课的教案"))
    check("scan 普通课题定级 L2", r2.get("level") == "L2")
    check("scan 普通课题 allowed", r2.get("allowed") is True)


def test_slot_propagation() -> None:
    """验证 contextvar 槽位能跨 task 回传 —— 这是响应头机制的前提。

    Starlette 的中间件与端点跑在不同 task 上：子 task 对 ContextVar 执行
    .set() 不会回传给父 task，但对同一个 dict 对象的原地修改是共享的。
    如果这个假设不成立，响应头就永远不会出现 X-Data-Level。
    """
    print("\n== 5. contextvar 槽位跨 task 回传（响应头机制的前提）==")
    import anyio
    import inspect

    async def main():
        slot = new_data_flow_slot()      # 中间件在请求开始时建槽

        async def endpoint():
            # 模拟子 task 里的端点写入
            set_data_flow({
                "level": "L3", "route": "cloud", "action": "warn",
                "egress": True, "allowed": True,
                "findings": [{"kind": "phone", "count": 1, "label": "手机号",
                              "level": "L3", "sample": "138****5678"}],
            })

        async with anyio.create_task_group() as tg:
            tg.start_soon(endpoint)
        # 注意：get_data_flow 必须在 task 上下文内读。
        # anyio.run 返回后外层 context 已丢弃，此时读必然是 None —— 这不是缺陷。
        return slot, get_data_flow()

    slot, in_task = anyio.run(main)
    check("父 task 能读到子 task 写入的 level", slot.get("level") == "L3",
          f"(实际 {slot.get('level')})")
    check("父 task 能读到 findings", bool(slot.get("findings")))
    check("task 内 get_data_flow 与槽位一致", (in_task or {}).get("level") == "L3")

    src = inspect.getsource(set_data_flow)
    check("set_data_flow 采用原地更新而非直接 .set()", "cur.update" in src)


def test_block_error() -> None:
    print("\n== 6. 阻断异常的可操作提示 ==")
    set_mode("enforce")
    d = decide(CLOUD, classify("联系家长 13812345678"), protocol="openai")
    check("阻断理由含定级", "L3" in d.reason, f"({d.reason})")
    err = DataEgressBlockedError(d.reason)
    check("异常带 E3006", err.code == "E3006", f"(实际 {err.code})")
    check("异常 HTTP 403", err.status == 403)
    check("异常 hint 指向改校内模型或移除信息",
          "校内" in (err.hint or "") and "个人信息" in (err.hint or ""),
          f"({err.hint})")
    print(f"      message = {err}")
    print(f"      hint    = {err.hint}")
    set_mode("warn")


def test_redact_keeps_pedagogy() -> None:
    print("\n== 7. 脱敏保留教学语义 ==")
    text = ("本次月考成绩：张三 85 李四 92 王五 78，掌握率 42%。"
            "其中《浮力》计算题错误率最高，需重点讲解。联系家长 13812345678")
    masked, n = redact(text)
    check("姓名已替换为占位", "张三" not in masked and "学生A" in masked)
    check("手机号已移除", "13812345678" not in masked)
    check("教学结论保留", "浮力" in masked and "错误率最高" in masked)
    check("统计数字保留", "42%" in masked)
    check("掌握率不被误当成学生名", "学生D" not in masked)
    check("替换计数 > 0", n > 0, f"(替换 {n} 处)")
    print(f"      脱敏后: {masked}")

    # 人数/比率不应被当成成绩名单
    clf = classify("本班 45 人，及格率 88%，平均分 76.5 分")
    check("纯统计描述不判为成绩名单",
          not any(f.kind == "score_table" for f in clf.findings),
          f"(定级 {clf.level})")


def main() -> int:
    print(f"策略模式: {get_safety_mode()}   (EDUFORGE_SAFETY_MODE)")
    test_classify()
    test_policy_matrix()
    test_sanitize_mode()
    test_call_paths_guarded()
    test_private_endpoint()
    test_api_functions()
    test_slot_propagation()
    test_block_error()
    test_redact_keeps_pedagogy()

    print(f"\n{'=' * 64}")
    print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    if FAIL:
        print("失败项：")
        for f in FAIL:
            print(f"  - {f}")
    print("=" * 64)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
