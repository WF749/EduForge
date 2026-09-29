"""教学蓝图 API：生成前的环节设计，供教师确认或直接跳过。

只有**一个**接口，故意保持很小：
蓝图是"生成前的对齐环节"，不是业务流程本身。把它塞进 lesson_plan 或
courseware 会让任何一个失败都拖垮另一个（lesson_tasks 的取舍文档里写过同样的理由）。

核心约定：**蓝图失败不能阻断正式生成**
--------------------------------------
因此本接口在**任何情况下都返回 success=True**：
  * 模型可用 → `source="model"`；
  * 模型失败 / 返回格式不对 → 回落离线骨架，`source="template"` + `degraded=True`
    + `error` 写明原因；
  * 教师点了"直接生成" → 前端根本不必调这个接口。

前端拿到 `degraded=True` 时应当提示原因，但**必须仍然允许继续生成**。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body
from fastapi.concurrency import run_in_threadpool

import logging

from ..services.course_knowledge import CourseKnowledge, build_course_context
from ..services.teaching_blueprint import (
    generate_blueprint, normalize_blueprint, validate_blueprint,
)
from ..services.teaching_intent import normalize_teaching_intent

router = APIRouter()
log = logging.getLogger("teaching_api")


@router.post("/teaching/blueprint", tags=["教学蓝图"])
async def generate_teaching_blueprint(body: Dict[str, Any] = Body(default={})):
    """按教学意图生成教学蓝图（课堂环节安排）。

    入参（**全部可选**）：
      * `teachingIntent` —— 教学意图；缺字段时按空处理，不报错
      * `knowledgeScope` —— system / personal / both / none，缺省 both
      * `provider` —— 指定模型提供方，留空用默认
      * `lessonId` / `topic` / `duration` —— 便于只传最少字段的调用方

    出参：
      * `success` —— **恒为 True**（蓝图失败不阻断）
      * `blueprint` —— 一定可用（模型失败时为离线骨架）
      * `degraded` / `error` —— 是否降级及原因
      * `knowledge` —— 本次检索情况：用上没有、范围、原因
    """
    # 蓝图是"锦上添花"，不是必经关卡：归一化与检索都在兜底之外会变成
    # 单点故障 —— 一个脏字段就让整个接口 500，而调用方（工作台）拿不到任何
    # 蓝图，只能退化成"没有蓝图直接生成"，等于这个功能白做。
    try:
        intent = normalize_teaching_intent(body.get("teachingIntent") or body)
    except Exception as e:  # noqa: BLE001
        log.warning("教学意图解析失败，按空意图继续: %s", e)
        intent = normalize_teaching_intent({})
    scope = body.get("knowledgeScope") or "both"
    provider = body.get("provider")
    lesson_id = str(body.get("lessonId") or "")[:64]

    # 蓝图也要用知识：不然环节设计会脱离本课知识点，
    # 后面四路生成照着它走，就会一起跑偏。
    try:
        knowledge = build_course_context(
            topic=intent.topic or str(body.get("topic") or ""),
            subject=intent.subject,
            grade=intent.grade,
            kind="lesson_plan",
            scope=scope,
            lesson_id=lesson_id,
        )
    except Exception as e:  # noqa: BLE001 —— 检索失败不得阻断蓝图
        log.warning("蓝图用知识检索失败，本次不带知识: %s", e)
        knowledge = CourseKnowledge(scope=scope)
        knowledge.reason = "知识库检索失败，本次未使用知识库"

    # llm_service.chat 是同步的，直接 await 会把整个事件循环堵住几秒；
    # 丢到线程池里跑（FastAPI 自带，不新增依赖）。
    try:
        blueprint = await run_in_threadpool(
            generate_blueprint,
            intent,
            knowledge_text=knowledge.text,
            provider=provider,
            lesson_id=lesson_id,
            topic=str(body.get("topic") or ""),
            duration=intent.duration,
        )
    except Exception as e:  # noqa: BLE001 —— 见模块说明：恒返回可用蓝图
        log.warning("蓝图生成异常，已回落到离线骨架: %s", e)
        from ..services.teaching_blueprint import template_blueprint
        blueprint = template_blueprint(
            str(body.get("topic") or ""), intent.duration,
            intent=intent, lesson_id=lesson_id)
        blueprint.error = f"蓝图生成失败：{type(e).__name__}"

    degraded = blueprint.source != "model"
    return {
        "success": True,
        "degraded": degraded,
        "error": blueprint.error,
        "blueprint": blueprint.to_dict(),
        "teachingIntent": intent.to_dict(),
        "knowledge": knowledge.to_dict(),
    }


@router.post("/teaching/blueprint/validate", tags=["教学蓝图"])
async def validate_teaching_blueprint(body: Dict[str, Any] = Body(default={})):
    """校验教师改过的蓝图，**只返回提示，不做任何拦截**。

    教师在蓝图面板里增删改环节之后调它，拿到提示自己决定要不要改。
    """
    blueprint = normalize_blueprint(body.get("teachingBlueprint") or {})
    intent = normalize_teaching_intent(body.get("teachingIntent") or {})
    warnings = validate_blueprint(blueprint, intent)
    return {
        "success": True,
        "warnings": warnings,
        "totalMinutes": blueprint.totalMinutes
        or sum(s.minutes for s in blueprint.stages),
        "stageCount": len(blueprint.stages),
    }
