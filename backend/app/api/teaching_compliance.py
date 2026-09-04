"""教学合规校验器 API（路线图 #3 · v1）

离线、规则化地对 AI 生成的教学产物做合规扫描。
不调用大模型，零额度消耗；可作为生成后的"质检闸门"。
"""
from fastapi import APIRouter, Body
from typing import Any, Dict, List, Optional

from ..services.teaching_compliance import teaching_compliance_checker

router = APIRouter()


@router.post("/teaching-compliance/check", tags=["教学合规校验器"])
async def check_teaching_compliance(
    artifact_type: str = Body(..., description="产物类型: lesson_plan/ppt/courseware/game/animation"),
    content: str = Body(..., description="产物的纯文本（调用方负责把结构化字段拼成文本）"),
    meta: Optional[Dict[str, Any]] = Body(
        None,
        description="可选上下文: {level, subject, grade, topic, duration}",
        examples={"示例": {"level": "初中", "subject": "物理", "grade": "八年级", "topic": "浮力", "duration": 45}},
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
