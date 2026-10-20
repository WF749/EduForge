"""教学合规校验器 API（路线图 #3 · v1）

离线、规则化地对 AI 生成的教学产物做合规扫描。
不调用大模型，零额度消耗；可作为生成后的"质检闸门"。

另有一个**可选**的模型深度复查（`/teaching-compliance/review`）：
它调模型、慢、会抖，所以默认关闭且必须手动触发，只报告不改写。
"""
from fastapi import APIRouter, Body
from typing import Any, Dict, List, Optional

from ..services.teaching_compliance import teaching_compliance_checker
from ..services import teaching_review, artifact_versions
from ..services.teaching_compliance import flatten_to_text

router = APIRouter()


@router.post("/teaching-compliance/check", tags=["教学合规校验器"])
async def check_teaching_compliance(
    artifact_type: str = Body(..., description="产物类型: lesson_plan/ppt/courseware/game/animation"),
    content: str = Body(..., description="产物的纯文本（调用方负责把结构化字段拼成文本）"),
    meta: Optional[Dict[str, Any]] = Body(
        None,
        description="可选上下文: {level, subject, grade, topic, duration}",
        # ⚠️ examples 必须是**列表**，不能是 dict。
        # 写成 examples={"示例": {...}} 会让 FastAPI 生成的 OpenAPI schema 里
        # examples 变成对象，进而导致 /openapi.json 直接 500（/docs 打不开）。
        examples=[{"level": "初中", "subject": "物理", "grade": "八年级",
                   "topic": "浮力", "duration": 45}],
    ),
):
    """对一份教学产物做离线合规扫描，返回问题清单与修改建议。"""
    try:
        report = teaching_compliance_checker.check(artifact_type, content, meta or {})
        return {
            "success": True,
            "message": "合规扫描完成",
            "report": report.to_dict(),
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"合规扫描失败: {str(e)}",
        }


@router.post("/teaching-compliance/review", tags=["教学合规校验器"])
async def review_teaching_artifact(
    artifact_type: str = Body("lesson_plan", description="产物类型，目前只对教案有意义"),
    content: str = Body("", description="产物纯文本；留空时从下面 lesson_id 的版本链读"),
    lesson_id: Optional[str] = Body(None, description="课程 ID，配合 kind 读当前版本"),
    kind: str = Body("lesson_plan", description="版本链里的成品类型"),
    meta: Optional[Dict[str, Any]] = Body(None, description="可选上下文 {level, topic, duration}"),
    provider: Optional[str] = Body(None, description="指定模型提供方，留空用默认"),
):
    """规则闸门之后的**可选**模型深度复查（默认关闭、手动触发、只报告）。

    规则（R1–R8）查"有没有、合不合规范"；这个查"好不好、能不能真的落地"
    ——45 分钟做不完、目标没有活动支撑、检测覆盖不到目标这类规则写不出来的问题。

    未开启时不报错，返回 enabled=False 与原因，前端如实显示"未开启"即可。
    """
    text = (content or "").strip()

    # 没直接给文本就从版本链取当前版本 —— 教师通常就是想复查"现在这一版"
    if not text and lesson_id:
        try:
            got = artifact_versions.get_content(lesson_id, kind)
            text = flatten_to_text(got) if got is not None else ""
        except Exception:  # noqa: BLE001 —— 取不到就当没内容，由后面如实报出
            text = ""

    if not text:
        return {
            "success": False,
            "message": "没有可复查的内容：请传 content，或传 lesson_id + kind 从版本链读取",
            "review": {"enabled": False, "reason": "内容为空", "findings": []},
        }

    review = teaching_review.review_text(text, meta=meta, provider=provider)
    return {
        "success": True,
        "message": "深度复查完成" if review.get("enabled") else (review.get("reason") or "未执行"),
        "artifact_type": artifact_type,
        "review": review,
    }
