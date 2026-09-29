# 教案生成相关API
# 支持全学段教案生成的完整流程

from fastapi import APIRouter, Body, Query, Path, HTTPException
from fastapi.responses import FileResponse
from typing import Optional, List, Dict, Any
from urllib.parse import quote
from ..document_extract import resolve_uploaded_references
from ..paths import GENERATED_LP
from ..services import artifact_versions
from ..services.llm_lesson_plan_all_stages import LessonPlanGenerator
from ..services.university_major_config import UniversityMajorConfig
from ..services.course_knowledge import compose_generation_context
from ..services.teaching_compliance import (
    flatten_to_text,
    pick_assessment_text,
    run_compliance_gate,
)
import json
import os

router = APIRouter()

# 教案生成器实例
lesson_plan_generator = LessonPlanGenerator()

# 输出目录
LESSON_PLAN_DIR = str(GENERATED_LP)

# 确保输出目录存在
os.makedirs(LESSON_PLAN_DIR, exist_ok=True)


# ==================== 教案生成流程 API ====================

@router.post("/lesson-plan/analyze-requirements", tags=["教案-全学段流程"])
async def analyze_lesson_plan_requirements(
    level: str = Body(..., description="学段"),
    subject: str = Body(..., description="学科/专业"),
    grade: str = Body(..., description="年级/课型"),
    topic: str = Body(..., description="教学主题"),
    duration: int = Body(45, description="授课时长（分钟）"),
    requirements: str = Body("", description="补充需求")
):
    """阶段1：全学段需求解析与合规校验"""
    try:
        result = lesson_plan_generator.analyze_requirements(
            level=level,
            subject=subject,
            grade=grade,
            topic=topic,
            duration=duration,
            requirements=requirements
        )

        return {
            "success": True,
            "message": "需求解析成功",
            "requirements": result
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"需求解析失败: {str(e)}"
        }


@router.post("/lesson-plan/generate-outline", tags=["教案-全学段流程"])
async def generate_lesson_plan_outline(
    requirements: Dict[str, Any] = Body(..., description="需求执行清单")
):
    """阶段2：教案结构化大纲生成"""
    try:
        outline = lesson_plan_generator.generate_outline(requirements)

        return {
            "success": True,
            "message": "大纲生成成功",
            "outline": outline
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"大纲生成失败: {str(e)}"
        }


@router.post("/lesson-plan/generate-detailed-content", tags=["教案-全学段流程"])
async def generate_lesson_plan_content(
    outline: Dict[str, Any] = Body(..., description="教案大纲"),
    requirements: Dict[str, Any] = Body(..., description="需求执行清单")
):
    """阶段3：分模块精细化内容生成"""
    try:
        lesson_plan = lesson_plan_generator.generate_detailed_content(outline, requirements)

        return {
            "success": True,
            "message": "精细化内容生成成功",
            "lesson_plan": lesson_plan
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"精细化内容生成失败: {str(e)}"
        }


@router.post("/lesson-plan/validate-compliance", tags=["教案-全学段流程"])
async def validate_lesson_plan_compliance(
    lesson_plan: Dict[str, Any] = Body(..., description="教案内容"),
    level: str = Body(..., description="学段"),
    subject: str = Body(..., description="学科/专业")
):
    """阶段4：教学合规性与学段/专业适配性双重校验"""
    try:
        validation_result = lesson_plan_generator.validate_compliance(lesson_plan, level, subject)

        return {
            "success": True,
            "message": "合规性校验成功",
            "validation_report": validation_result["validation_report"],
            "corrected_lesson_plan": validation_result["corrected_lesson_plan"]
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"合规性校验失败: {str(e)}"
        }


def _merge_missing_modules(base: Dict[str, Any], modified: Dict[str, Any]):
    """模型漏掉的模块用原版补回，返回 (合并结果, 被补回的模块名)。

    为什么不直接信模型：教案有 12 个模块，模型做"增量修改"时经常只回它改动的
    那几个模块，其余直接省略。早期 `_ensure_content_completeness` 的教训是——
    遇到缺项就置空，会让教师看到"改完少了一半"。这里反过来：**缺了就补旧的**，
    宁可保留没改到的原文，也不能让内容凭空消失。补回了什么如实写进 change_log。
    """
    merged = dict(modified)
    filled = []
    for key, value in (base or {}).items():
        current = merged.get(key)
        empty = current is None or current == "" or current == [] or current == {}
        if key not in merged or empty:
            if value not in (None, "", [], {}):
                merged[key] = value
                filled.append(key)
    return merged, filled


@router.post("/lesson-plan/revise", tags=["教案-迭代修改"])
async def revise_lesson_plan(
    lesson_id: str = Body(..., description="课程 id（决定改的是哪一节课的教案）"),
    instruction: str = Body(..., description="修改指令，例如「第三段太难，换成生活里的例子」"),
    level: str = Body(..., description="学段"),
    subject: str = Body(..., description="学科/专业"),
    grade: str = Body(..., description="年级/课型"),
    base_version: Optional[int] = Body(None, description="基于哪一版修改，默认当前版本"),
    duration: Optional[int] = Body(None, description="课时（用于合规复检，可省略）"),
):
    """按教师的一句话指令增量修改教案，并把结果记为新版本。

    与旧的 ``/lesson-plan/modify`` 的三点区别：
      1. 基线从版本链里读，不由前端回传 —— 刷新/换设备后仍知道在改哪一版；
      2. 结果落盘为新版本，可回退（改坏了能回到上一版）；
      3. 模型没给出完整教案时**不覆盖**，保留原版本并如实报错，
         避免重演"生成成功但内容全空"那类静默事故。
    """
    # FastAPI 的 Body(...) 默认值在被**直接调用**（测试、内部复用）时拿到的是 Body 对象
    # 而不是 None，直接往下传会在 int() 处炸。这里按 project 既有做法归一化。
    if base_version is not None and not isinstance(base_version, int):
        base_version = None
    if duration is not None and not isinstance(duration, int):
        duration = None

    instruction = (instruction or "").strip()
    if not instruction:
        return {"success": False, "message": "请说明要改什么，例如「把导入环节换成生活实例」"}

    try:
        base = artifact_versions.get_content(lesson_id, "lesson_plan", base_version)
    except Exception as e:  # noqa: BLE001 - id/kind 非法也算"改不了"，如实返回
        return {"success": False, "message": f"读取基线版本失败: {e}"}

    if not isinstance(base, dict) or not base:
        return {
            "success": False,
            "message": "这门课还没有可修改的教案版本，请先生成教案",
        }

    try:
        result = lesson_plan_generator.modify_lesson_plan(
            existing_lesson_plan=base,
            level=level,
            subject=subject,
            grade=grade,
            modification_requirements=instruction,
        )
    except Exception as e:
        return {"success": False, "message": f"教案修改失败: {e}"}

    result = result if isinstance(result, dict) else {}
    modified = result.get("modified_lesson_plan")

    if not isinstance(modified, dict) or not modified:
        return {
            "success": False,
            "message": "模型没有返回修改后的完整教案，已保留原版本（原版本未被改动）",
            "detail": {
                "raw_keys": list(result.keys()),
                "change_log": result.get("change_log"),
            },
        }

    merged, filled = _merge_missing_modules(base, modified)

    try:
        version_info = artifact_versions.save_version(
            lesson_id, "lesson_plan", merged, note=instruction, author="model"
        )
    except Exception as e:
        return {"success": False, "message": f"修改已生成但存版本失败: {e}"}

    compliance = run_compliance_gate(
        "lesson_plan",
        merged,
        {
            "level": level, "subject": subject, "grade": grade, "duration": duration,
            "objectives_text": flatten_to_text(merged.get("教学目标")),
            "assessment_text": pick_assessment_text(merged),
        },
    )

    change_log = result.get("change_log")
    if not isinstance(change_log, list):
        change_log = []
    if filled:
        change_log = list(change_log) + [f"自动保留未改动的模块：{'、'.join(filled)}"]

    return {
        "success": True,
        "message": f"已按指令修改并记为 v{version_info['version']}",
        "lesson_plan": merged,
        "version": version_info,
        "change_log": change_log,
        "ppt_modification_suggestions": result.get("ppt_modification_suggestions"),
        "compliance": compliance,
    }


@router.post("/lesson-plan/export", tags=["教案-全学段流程"])
async def export_lesson_plan(
    lesson_plan: Dict[str, Any] = Body(..., description="教案内容"),
    export_format: str = Body("json", description="导出格式: json, docx, pdf"),
    topic: str = Body(None, description="主题（用于文件名）")
):
    """阶段6：多格式导出与跨模块内容同步"""
    try:
        exported_content = lesson_plan_generator.export_lesson_plan(
            lesson_plan, export_format, output_dir=LESSON_PLAN_DIR, topic=topic
        )

        if export_format in ("docx", "pdf"):
            # docx/pdf 格式直接返回文件路径（已由 export 方法生成）
            file_path = exported_content
            filename = os.path.basename(file_path)
        else:
            # json 格式需要手动写入文件
            topic = lesson_plan.get("教案基本信息", {}).get("课题", "教案")
            sanitized_topic = topic.replace('/', '_').replace('\\', '_')
            filename = f"{sanitized_topic}.{export_format}"
            file_path = os.path.join(LESSON_PLAN_DIR, filename)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(exported_content)

        return {
            "success": True,
            "message": "教案导出成功",
            "file_path": file_path,
            "filename": filename,
            "download_url": f"/api/lesson-plan/download?filename={quote(filename)}",
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"教案导出失败: {str(e)}"
        }


@router.post("/lesson-plan/generate-from-ppt", tags=["教案-全学段流程"])
async def generate_lesson_plan_from_ppt(
    ppt_content: str = Body(..., description="PPT课件内容"),
    level: str = Body(..., description="学段"),
    subject: str = Body(..., description="学科/专业"),
    grade: str = Body(..., description="年级/课型"),
    topic: str = Body(..., description="教学主题"),
    duration: int = Body(45, description="授课时长（分钟）")
):
    """从PPT生成匹配的教案"""
    try:
        lesson_plan = lesson_plan_generator.generate_from_ppt(
            ppt_content=ppt_content,
            level=level,
            subject=subject,
            grade=grade,
            topic=topic,
            duration=duration
        )

        return {
            "success": True,
            "message": "从PPT生成教案成功",
            "lesson_plan": lesson_plan
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"从PPT生成教案失败: {str(e)}"
        }


@router.post("/lesson-plan/generate-full", tags=["教案-全学段流程"])
async def generate_full_lesson_plan(
    level: str = Body(..., description="学段"),
    subject: str = Body(..., description="学科/专业"),
    grade: str = Body(..., description="年级/课型"),
    topic: str = Body(..., description="教学主题"),
    duration: int = Body(45, description="授课时长（分钟）"),
    requirements: str = Body("", description="补充需求"),
    reference_files: Optional[List[str]] = Body(None, description="上传参考资料的文件ID"),
    lesson_id: Optional[str] = Body(None, description="所属课程 id（给了就把成品存为该课教案的 v1）"),
    # 下面三个是 2026-09-25 新增的**可选**字段：不传就与以前完全一样
    teaching_intent: Optional[Dict[str, Any]] = Body(
        None, description="教学意图（可选）"),
    teaching_blueprint: Optional[Dict[str, Any]] = Body(
        None, description="教学蓝图（可选；不传表示教师跳过了蓝图）"),
    knowledge_scope: Optional[str] = Body(
        "both", description="知识库范围：system/personal/both/none")
):
    """完整教案生成流程"""
    try:
        # 阶段1：需求解析与合规校验
        reference_text = "\n\n".join(resolve_uploaded_references(reference_files))
        effective_requirements = requirements
        if reference_text:
            effective_requirements = (
                f"{requirements}\n\n【参考资料摘录】\n{reference_text}"
            ).strip()
        # 四路生成共用同一份课程上下文（见 app/services/course_knowledge.py
        # 的 compose_generation_context）—— 知识 + 教学意图 + 教学蓝图一次拼好，
        # 保证四类产物拿到的是**同一段**上下文。
        # 检索失败、蓝图缺失都不阻断生成 —— 最多是这次没用到它们。
        course_knowledge, composed_context, ctx_meta = compose_generation_context(
            topic=topic, subject=subject, grade=grade, kind="lesson_plan",
            scope=knowledge_scope, intent=teaching_intent,
            blueprint=teaching_blueprint, lesson_id=lesson_id,
        )
        effective_requirements = (
            f"{effective_requirements}\n\n{composed_context}".strip()
            if composed_context else effective_requirements
        )

        requirements_result = lesson_plan_generator.analyze_requirements(
            level=level,
            subject=subject,
            grade=grade,
            topic=topic,
            duration=duration,
            requirements=effective_requirements
        )

        # 阶段2：教案结构化大纲生成
        outline = lesson_plan_generator.generate_outline(requirements_result)

        # 阶段3：分模块精细化内容生成
        lesson_plan = lesson_plan_generator.generate_detailed_content(outline, requirements_result)

        # 阶段4：教学合规性与学段/专业适配性双重校验
        validation_result = lesson_plan_generator.validate_compliance(lesson_plan, level, subject)
        corrected_lesson_plan = validation_result["corrected_lesson_plan"]

        # 阶段5：出厂质检闸门（纯规则离线扫描，只报告不阻断）
        compliance = run_compliance_gate(
            "lesson_plan",
            corrected_lesson_plan,
            {
                "level": level, "subject": subject, "grade": grade,
                "topic": topic, "duration": duration,
                # 单独把教学目标交给 R7（行为动词可测量）精确检查，
                # 而不是让规则在全文里猜哪一段是教学目标 —— 那会误报。
                "objectives_text": flatten_to_text(
                    corrected_lesson_plan.get("教学目标")
                ),
                # R8（教学评一致性）同理：检测/评价模块名不固定，
                # 由 pick_assessment_text 按候选名取第一个有内容的。
                "assessment_text": pick_assessment_text(corrected_lesson_plan),
            },
        )

        # 阶段6：把成品存为该课教案的版本链起点
        # 存版本失败不能让"生成"失败——内容已经在手里了，丢掉版本只是少了回退能力，
        # 但让生成接口报错等于白跑一次模型。失败如实挂在 version_error 上。
        version_info = None
        version_error = None
        if lesson_id:
            try:
                version_info = artifact_versions.save_version(
                    lesson_id, "lesson_plan", corrected_lesson_plan,
                    note=f"首次生成：{topic}", author="model",
                )
            except Exception as e:  # noqa: BLE001 - 见上方说明
                version_error = str(e)

        return {
            "success": True,
            "message": "完整教案生成成功",
            "process": {
                "requirements": requirements_result,
                "outline": outline,
                "validation_report": validation_result["validation_report"]
            },
            "lesson_plan": corrected_lesson_plan,
            "compliance": compliance,
            # 让教师看到这一版用到了知识库里的哪些依据（可溯源）
            "course_knowledge": course_knowledge.to_dict(),
            "knowledge": course_knowledge.to_dict(),
            "citations": course_knowledge.citations,
            # 蓝图摘要只回传状态，不回传正文（正文由蓝图接口单独管理）
            # 如实说明蓝图到底用上没有。此前只要"有蓝图文本"就报 used=True，
            # 而草稿/跳过的蓝图根本不会被注入 —— 教师会以为系统照着蓝图生成了。
            "teaching_blueprint": {
                **ctx_meta,
                "status": (teaching_blueprint or {}).get("status", "")
                if isinstance(teaching_blueprint, dict) else "",
            },
            "version": version_info,
            "version_error": version_error,
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"完整教案生成失败: {str(e)}"
        }


# ==================== 大学专业配置 API ====================

@router.get("/lesson-plan/university/majors", tags=["教案-大学专业"])
async def get_university_majors():
    """获取大学专业列表"""
    try:
        majors = UniversityMajorConfig.get_all_majors()

        return {
            "success": True,
            "message": "获取专业列表成功",
            "majors": majors
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"获取专业列表失败: {str(e)}"
        }


@router.get("/lesson-plan/university/disciplines", tags=["教案-大学专业"])
async def get_university_disciplines():
    """获取学科门类列表"""
    try:
        disciplines = UniversityMajorConfig.DISCIPLINES

        return {
            "success": True,
            "message": "获取学科门类列表成功",
            "disciplines": disciplines
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"获取学科门类列表失败: {str(e)}"
        }


@router.get("/lesson-plan/university/majors-by-discipline", tags=["教案-大学专业"])
async def get_majors_by_discipline(
    discipline_code: str = Query(..., description="学科门类代码")
):
    """按学科门类获取专业列表"""
    try:
        majors = UniversityMajorConfig.get_majors_by_discipline(discipline_code)

        return {
            "success": True,
            "message": "获取专业列表成功",
            "majors": majors
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"获取专业列表失败: {str(e)}"
        }


@router.get("/lesson-plan/university/major-config", tags=["教案-大学专业"])
async def get_major_config(
    major_name: str = Query(..., description="专业名称")
):
    """获取专业配置"""
    try:
        config = UniversityMajorConfig.get_major_config(major_name)

        return {
            "success": True,
            "message": "获取专业配置成功",
            "config": config
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"获取专业配置失败: {str(e)}"
        }


# ==================== 文件下载 API ====================

@router.get("/lesson-plan/download", tags=["教案-文件"])
async def download_lesson_plan(
    filename: str = Query(..., description="文件名")
):
    """下载生成的教案文件"""
    try:
        safe_name = os.path.basename(filename)
        if safe_name != filename:
            raise HTTPException(status_code=400, detail="文件名无效")
        file_path = os.path.join(LESSON_PLAN_DIR, safe_name)

        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="文件不存在")

        return FileResponse(
            path=file_path,
            filename=filename,
            media_type="application/octet-stream"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"下载失败: {str(e)}")


@router.get("/lesson-plan/files", tags=["教案-文件"])
async def list_lesson_plan_files():
    """列出生成的教案文件"""
    try:
        files = []
        if os.path.exists(LESSON_PLAN_DIR):
            for file_name in os.listdir(LESSON_PLAN_DIR):
                file_path = os.path.join(LESSON_PLAN_DIR, file_name)
                if os.path.isfile(file_path):
                    files.append({
                        "name": file_name,
                        "size": os.path.getsize(file_path),
                        "mtime": os.path.getmtime(file_path)
                    })

        return {
            "success": True,
            "message": "获取文件列表成功",
            "files": files
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"获取文件列表失败: {str(e)}"
        }
