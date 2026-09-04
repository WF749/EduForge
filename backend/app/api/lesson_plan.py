# 教案生成相关API
# 支持全学段教案生成的完整流程

from fastapi import APIRouter, Body, Query, Path, HTTPException
from fastapi.responses import FileResponse
from typing import Optional, List, Dict, Any
from ..paths import GENERATED_LP
from ..services.llm_lesson_plan_all_stages import LessonPlanGenerator
from ..services.university_major_config import UniversityMajorConfig
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


@router.post("/lesson-plan/modify", tags=["教案-全学段流程"])
async def modify_lesson_plan(
    existing_lesson_plan: Dict[str, Any] = Body(..., description="已有教案内容"),
    level: str = Body(..., description="学段"),
    subject: str = Body(..., description="学科/专业"),
    grade: str = Body(..., description="年级/课型"),
    modification_requirements: str = Body(..., description="修改需求")
):
    """阶段5：迭代修改与版本管理"""
    try:
        modification_result = lesson_plan_generator.modify_lesson_plan(
            existing_lesson_plan=existing_lesson_plan,
            level=level,
            subject=subject,
            grade=grade,
            modification_requirements=modification_requirements
        )

        return {
            "success": True,
            "message": "教案修改成功",
            "modification_result": modification_result
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"教案修改失败: {str(e)}"
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
            "filename": filename
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
    requirements: str = Body("", description="补充需求")
):
    """完整教案生成流程"""
    try:
        # 阶段1：需求解析与合规校验
        requirements_result = lesson_plan_generator.analyze_requirements(
            level=level,
            subject=subject,
            grade=grade,
            topic=topic,
            duration=duration,
            requirements=requirements
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

        return {
            "success": True,
            "message": "完整教案生成成功",
            "process": {
                "requirements": requirements_result,
                "outline": outline,
                "validation_report": validation_result["validation_report"]
            },
            "lesson_plan": corrected_lesson_plan,
            "compliance": compliance
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
        file_path = os.path.join(LESSON_PLAN_DIR, filename)

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
