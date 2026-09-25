"""课件生成相关API - 支持课件、游戏、动画下载"""
import os
import shutil
from urllib.parse import quote
from fastapi import APIRouter, Body, Query, Path, HTTPException
from fastapi.responses import FileResponse
from typing import Optional
from ..paths import GENERATED_ANIM, GENERATED_CW, GENERATED_GAMES, GENERATED_LP
from ..services.course_knowledge import build_course_context
from ..services.courseware_generator import CoursewareGenerator
from ..services.game_generator import GameGenerator
from ..services.animation_generator import AnimationGenerator
from ..services.teaching_compliance import run_compliance_gate
from ..services.offline_artifact import check_offline
from . import lesson_tasks as lesson_tasks_api

router = APIRouter()

# 与主项目 paths / Docker 挂载一致（绝对路径）
OUTPUT_DIR = str(GENERATED_CW)
GAMES_DIR = str(GENERATED_GAMES)
ANIMATIONS_DIR = str(GENERATED_ANIM)
LESSON_PLANS_DIR = str(GENERATED_LP)


# ==================== 课件生成 ====================

@router.post("/courseware/generate", tags=["课件"])
async def generate_courseware(
    topic: str = Body(..., description="课程主题"),
    duration: int = Body(45, description="课程时长（分钟）"),
    audience: str = Body("大学生", description="目标受众"),
    format: str = Body("PPT+Word", description="输出格式"),
    provider: Optional[str] = Body(None, description="LLM提供商"),
    template: str = Body("standard", description="课件模板"),
    subject: str = Body("general", description="学科类型"),
    theme_color: str = Body("蓝色系", description="主题色"),
    key_points: Optional[list] = Body(None, description="核心知识点"),
    reference_docs: Optional[list] = Body(None, description="参考文档")
):
    """生成课件 - 同时生成PPTX和DOCX文件"""
    try:
        generator = CoursewareGenerator(output_dir=OUTPUT_DIR)

        result = generator.generate(
            topic=topic,
            duration=duration,
            audience=audience,
            format=format,
            provider=provider,
            template=template,
            subject=subject,
            theme_color=theme_color,
            key_points=key_points,
            reference_docs=reference_docs
        )

        return {
            "success": True,
            "message": "课件生成成功",
            "task_id": result.get("task_id"),
            "result": {
                "topic": result.get("topic"),
                "duration": result.get("duration"),
                "audience": result.get("audience"),
                "template": result.get("template"),
                "subject": result.get("subject"),
                "teaching_style": result.get("teaching_style"),
                "lesson_plan": result.get("lesson_plan"),
                "ppt_content": result.get("ppt_content"),
                "animation_ideas": result.get("animation_ideas"),
                "interactive_games": result.get("interactive_games"),
                "files": result.get("files", {}),
                "task_dir": result.get("task_dir")
            }
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"生成失败: {str(e)}"
        }


# ==================== 互动游戏生成 ====================

@router.post("/courseware/game/generate", tags=["课件-游戏"])
async def generate_game(
    topic: str = Body(..., description="课程主题"),
    audience: str = Body("大学生", description="目标受众"),
    teaching_content: str = Body("", description="教学内容（可选）"),
    game_type: Optional[str] = Body(None, description="游戏类型"),
    provider: Optional[str] = Body(None, description="LLM提供商")
):
    """生成互动游戏"""
    try:
        generator = GameGenerator(output_dir=GAMES_DIR)

        # 四路生成共用同一份课程知识上下文（见 app/services/course_knowledge.py）
        course_knowledge = build_course_context(
            topic=topic, audience=audience, kind="game",
        )
        effective_content = teaching_content
        if not course_knowledge.empty:
            effective_content = f"{teaching_content}\n\n{course_knowledge.text}".strip()

        result = generator.generate(
            topic=topic,
            audience=audience,
            teaching_content=effective_content,
            game_type=game_type,
            provider=provider
        )

        game_payload = {
            "task_id": result.get("task_id"),
            "topic": result.get("topic"),
            "audience": result.get("audience"),
            "game_type": result.get("game_type"),
            "game_name": result.get("game_name"),
            "description": result.get("description"),
            "rules": result.get("rules"),
            "game_data": result.get("game_data"),
            "html_path": result.get("html_path"),
            "html_content": result.get("html_content"),
            "task_dir": result.get("task_dir")
        }

        # 出厂质检闸门（纯规则离线扫描，只报告不阻断）
        compliance = run_compliance_gate(
            "game",
            game_payload,
            {"level": audience, "topic": topic},
        )

        # 游戏 HTML 目前是模板渲染（离线安全），但模型只出 JSON 设计、
        # 将来若改成自由生成 HTML，这个检查会自动生效
        offline = check_offline(game_payload.get("html_content"))

        return {
            "success": True,
            "message": "游戏生成成功",
            "game": game_payload,
            "compliance": compliance,
            "offline": offline
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"游戏生成失败: {str(e)}"
        }


@router.get("/courseware/game/types", tags=["课件-游戏"])
async def get_game_types():
    """获取支持的游戏类型"""
    generator = GameGenerator(output_dir=GAMES_DIR)
    return {
        "success": True,
        "types": generator.get_game_types()
    }


@router.get("/courseware/game/download", tags=["课件-游戏"])
async def download_game(
    task_id: Optional[str] = Query(None, description="任务ID"),
    task_dir: Optional[str] = Query(None, description="任务目录"),
    topic: Optional[str] = Query(None, description="课程主题")
):
    """下载游戏文件"""
    try:
        file_path = None

        if task_id and os.path.exists(GAMES_DIR):
            suffix = f"_{task_id}"
            for item in sorted(os.listdir(GAMES_DIR), reverse=True):
                if not item.endswith(suffix):
                    continue
                candidate_dir = os.path.join(GAMES_DIR, item)
                if os.path.isdir(candidate_dir):
                    task_dir = candidate_dir
                    break

        if task_dir and os.path.exists(task_dir):
            for f in os.listdir(task_dir):
                if f.endswith('.html') and 'game' in f.lower():
                    file_path = os.path.join(task_dir, f)
                    break

        if not file_path and topic:
            topic_clean = topic.replace('/', '_').replace('\\', '_')
            if os.path.exists(GAMES_DIR):
                for item in sorted(os.listdir(GAMES_DIR), reverse=True):
                    if topic_clean in item:
                        item_dir = os.path.join(GAMES_DIR, item)
                        if os.path.isdir(item_dir):
                            for f in os.listdir(item_dir):
                                if f.endswith('.html') and 'game' in f.lower():
                                    file_path = os.path.join(item_dir, f)
                                    break
                        if file_path:
                            break

        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="游戏文件不存在")

        filename = os.path.basename(file_path)

        return FileResponse(
            path=file_path,
            filename=filename,
            media_type="text/html"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"下载失败: {str(e)}")


# ==================== 动画演示生成 ====================

@router.post("/courseware/animation/generate", tags=["课件-动画"])
async def generate_animation(
    topic: str = Body(..., description="课程主题"),
    subject: str = Body("general", description="学科类型"),
    audience: str = Body("大学生", description="目标受众"),
    teaching_content: str = Body("", description="教学内容（可选）"),
    duration: int = Body(5, description="动画时长（分钟）"),
    style: str = Body("auto", description="动画风格：与 /animation/styles 一致"),
    provider: Optional[str] = Body(None, description="LLM提供商")
):
    """生成动画演示"""
    try:
        generator = AnimationGenerator(output_dir=ANIMATIONS_DIR)

        subject_name = {
            "mathematics": "数学", "physics": "物理", "chemistry": "化学",
            "biology": "生物", "geography": "地理", "general": "综合",
        }.get(subject, subject)
        # 四路生成共用同一份课程知识上下文（见 app/services/course_knowledge.py）
        course_knowledge = build_course_context(
            topic=topic, subject=subject, audience=audience, kind="animation",
        )
        content_with_subject = f"学科：{subject_name}\n{teaching_content}".strip()
        if not course_knowledge.empty:
            content_with_subject = f"{content_with_subject}\n\n{course_knowledge.text}"
        result = generator.generate(
            topic=topic,
            audience=audience,
            teaching_content=content_with_subject,
            duration=duration,
            provider=provider,
            style=style or "auto",
        )

        animation_payload = {
            "task_id": result.get("task_id"),
            "topic": result.get("topic"),
            "audience": result.get("audience"),
            "duration": result.get("duration"),
            "animation_data": result.get("animation_data"),
            "html_path": result.get("html_path"),
            "html_content": result.get("html_content"),
            "task_dir": result.get("task_dir"),
            "generation_method": result.get("generation_method"),
            "style_applied": "智能生成",
            "subject": result.get("subject") or subject,
            "knowledge_points": result.get("knowledge_points", []),
            "scenes": result.get("scenes", []),
        }

        # 出厂质检闸门（纯规则离线扫描，只报告不阻断）
        compliance = run_compliance_gate(
            "animation",
            animation_payload,
            {"level": audience, "topic": topic, "duration": duration},
        )

        # 离线可用性：模型被要求不许引 CDN，但它不总听话。
        # 拷到没网的教室电脑上才发现打不开就晚了，所以这里当场扫一遍（只报告不阻断）。
        offline = check_offline(animation_payload.get("html_content"))

        return {
            "success": True,
            "message": "动画生成成功",
            "animation": animation_payload,
            "compliance": compliance,
            "offline": offline
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"动画生成失败: {str(e)}"
        }


@router.get("/courseware/animation/styles", tags=["课件-动画"])
async def get_animation_styles():
    """获取支持的动画风格"""
    generator = AnimationGenerator(output_dir=ANIMATIONS_DIR)
    return {
        "success": True,
        "styles": generator.get_animation_styles()
    }


@router.get("/courseware/animation/download", tags=["课件-动画"])
async def download_animation(
    task_id: Optional[str] = Query(None, description="任务ID"),
    task_dir: Optional[str] = Query(None, description="任务目录"),
    topic: Optional[str] = Query(None, description="课程主题")
):
    """下载动画文件"""
    try:
        file_path = None

        if task_id and os.path.exists(ANIMATIONS_DIR):
            suffix = f"_{task_id}"
            for item in sorted(os.listdir(ANIMATIONS_DIR), reverse=True):
                if not item.endswith(suffix):
                    continue
                candidate_dir = os.path.join(ANIMATIONS_DIR, item)
                if os.path.isdir(candidate_dir):
                    task_dir = candidate_dir
                    break

        if task_dir and os.path.exists(task_dir):
            candidates = []
            for f in os.listdir(task_dir):
                if not f.endswith('.html'):
                    continue
                full = os.path.join(task_dir, f)
                if 'animation' in f.lower():
                    file_path = full
                    break
                candidates.append(full)
            if not file_path and candidates:
                file_path = candidates[0]

        if not file_path and topic:
            topic_clean = topic.replace('/', '_').replace('\\', '_')
            if os.path.exists(ANIMATIONS_DIR):
                for item in sorted(os.listdir(ANIMATIONS_DIR), reverse=True):
                    if topic_clean in item:
                        item_dir = os.path.join(ANIMATIONS_DIR, item)
                        if os.path.isdir(item_dir):
                            for f in os.listdir(item_dir):
                                if f.endswith('.html') and 'animation' in f.lower():
                                    file_path = os.path.join(item_dir, f)
                                    break
                        if file_path:
                            break

        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="动画文件不存在")

        filename = os.path.basename(file_path)

        return FileResponse(
            path=file_path,
            filename=filename,
            media_type="text/html"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"下载失败: {str(e)}")


# ==================== 文件下载 ====================

@router.get("/courseware/download/{file_type}", tags=["课件"])
async def download_file(
    file_type: str = Path(..., description="文件类型: pptx, docx, json"),
    task_id: Optional[str] = Query(None, description="任务ID"),
    task_dir: Optional[str] = Query(None, description="任务目录路径"),
    topic: Optional[str] = Query(None, description="课程主题（用于查找最新文件）")
):
    """下载生成的文件"""
    try:
        file_path = None

        if task_dir:
            if file_type == "pptx":
                for f in os.listdir(task_dir):
                    if f.endswith('.pptx'):
                        file_path = os.path.join(task_dir, f)
                        break
            elif file_type == "docx":
                for f in os.listdir(task_dir):
                    if f.endswith('.docx'):
                        file_path = os.path.join(task_dir, f)
                        break
            elif file_type == "json":
                file_path = os.path.join(task_dir, "courseware_data.json")

        if not file_path and topic:
            topic_clean = topic.replace('/', '_').replace('\\', '_')
            if os.path.exists(OUTPUT_DIR):
                for item in sorted(os.listdir(OUTPUT_DIR), reverse=True):
                    if topic_clean in item:
                        item_dir = os.path.join(OUTPUT_DIR, item)
                        if os.path.isdir(item_dir):
                            if file_type == "pptx":
                                for f in os.listdir(item_dir):
                                    if f.endswith('.pptx'):
                                        file_path = os.path.join(item_dir, f)
                                        break
                            elif file_type == "docx":
                                for f in os.listdir(item_dir):
                                    if f.endswith('.docx'):
                                        file_path = os.path.join(item_dir, f)
                                        break
                            elif file_type == "json":
                                file_path = os.path.join(item_dir, "courseware_data.json")
                            if file_path:
                                break

        # 对于docx，也在教案生成目录中查找
        if not file_path and file_type == "docx" and os.path.exists(LESSON_PLANS_DIR):
            if topic:
                topic_clean = topic.replace('/', '_').replace('\\', '_')
                for f in sorted(os.listdir(LESSON_PLANS_DIR), reverse=True):
                    if f.endswith('.docx') and topic_clean in f:
                        file_path = os.path.join(LESSON_PLANS_DIR, f)
                        break
            if not file_path:
                docx_files = [f for f in os.listdir(LESSON_PLANS_DIR) if f.endswith('.docx')]
                if docx_files:
                    docx_files.sort(key=lambda x: os.path.getmtime(os.path.join(LESSON_PLANS_DIR, x)), reverse=True)
                    file_path = os.path.join(LESSON_PLANS_DIR, docx_files[0])

        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"文件不存在: {file_type}")

        media_types = {
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "json": "application/json"
        }

        filename = os.path.basename(file_path)

        return FileResponse(
            path=file_path,
            filename=filename,
            media_type=media_types.get(file_type, "application/octet-stream")
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"下载失败: {str(e)}")


# ==================== 其他端点 ====================

@router.get("/courseware/preview", tags=["课件"])
async def preview_courseware(
    topic: str = Query(..., description="课程主题"),
    provider: Optional[str] = Query(None, description="LLM提供商")
):
    """预览课件大纲"""
    try:
        generator = CoursewareGenerator(output_dir=OUTPUT_DIR)
        outline = generator.generate_outline(topic=topic, provider=provider, subject="general")

        return {
            "success": True,
            "message": "大纲生成成功",
            "outline": outline
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"生成大纲失败: {str(e)}"
        }


@router.get("/courseware/templates", tags=["课件"])
async def get_courseware_templates():
    """获取课件模板列表"""
    try:
        generator = CoursewareGenerator(output_dir=OUTPUT_DIR)
        templates = generator.get_templates()

        return {
            "success": True,
            "templates": templates
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"获取模板失败: {str(e)}"
        }


@router.get("/courseware/files", tags=["课件"])
async def list_files(
    topic: Optional[str] = Query(None, description="课程主题（可选，用于过滤）")
):
    """列出生成的文件"""
    try:
        files = []
        # 反查表：把产物归到它所属的那节课（读不到就按"未归档"展示，不影响列表）
        index = lesson_tasks_api.build_file_index()

        sources = [
            (OUTPUT_DIR, "课件", "generated_courseware"),
            (GAMES_DIR, "游戏", "generated_games"),
            (ANIMATIONS_DIR, "动画", "generated_animations"),
        ]
        for dir_name, dir_label, mount_name in sources:
            if os.path.exists(dir_name):
                for item in sorted(os.listdir(dir_name), reverse=True):
                    item_dir = os.path.join(dir_name, item)
                    if os.path.isdir(item_dir):
                        if topic and topic.replace('/', '_').replace('\\', '_') not in item:
                            continue

                        item_files = []
                        for f in os.listdir(item_dir):
                            if f.endswith(('.pptx', '.docx', '.json', '.html')):
                                artifact_url = f"/{mount_name}/{quote(item)}/{quote(f)}"
                                item_files.append({
                                    "name": f,
                                    "type": f.split('.')[-1],
                                    "size": os.path.getsize(os.path.join(item_dir, f)),
                                    "download_url": artifact_url,
                                    "preview_url": artifact_url if f.endswith('.html') else None,
                                })

                        if item_files:
                            files.append({
                                "dir": item,
                                "label": dir_label,
                                "delete_url": f"/api/courseware/files/{quote(item)}?source={quote(mount_name)}",
                                "files": item_files,
                                "lesson": index["dirs"].get(item)
                            })

        if os.path.exists(LESSON_PLANS_DIR):
            for filename in sorted(os.listdir(LESSON_PLANS_DIR), reverse=True):
                file_path = os.path.join(LESSON_PLANS_DIR, filename)
                if not os.path.isfile(file_path) or not filename.endswith(('.docx', '.pdf', '.json')):
                    continue
                artifact_url = f"/api/lesson-plan/download?filename={quote(filename)}"
                files.append({
                    "dir": os.path.splitext(filename)[0],
                    "label": "教案",
                    "delete_url": None,
                    "files": [{
                        "name": filename,
                        "type": filename.rsplit('.', 1)[-1],
                        "size": os.path.getsize(file_path),
                        "download_url": artifact_url,
                        "preview_url": None,
                    }],
                    "lesson": index["files"].get(filename),
                })

        return {
            "success": True,
            "files": files
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"获取文件列表失败: {str(e)}"
        }


@router.delete("/courseware/files/{dir_name}", tags=["课件"])
async def delete_generated_dir(
    dir_name: str,
    source: Optional[str] = Query(None, description="生成目录挂载名，可选"),
):
    """删除指定的生成目录及其中所有文件"""
    import shutil
    try:
        deleted = False
        source_dirs = {
            "generated_courseware": OUTPUT_DIR,
            "generated_games": GAMES_DIR,
            "generated_animations": ANIMATIONS_DIR,
        }
        base_dirs = [source_dirs[source]] if source in source_dirs else [OUTPUT_DIR, GAMES_DIR, ANIMATIONS_DIR]
        for base_dir in base_dirs:
            target = os.path.join(base_dir, dir_name)
            real_target = os.path.realpath(target)
            real_base = os.path.realpath(base_dir)
            try:
                inside_base = os.path.commonpath([real_target, real_base]) == real_base
            except ValueError:
                inside_base = False
            if not inside_base:
                raise HTTPException(status_code=403, detail="路径无效")
            if os.path.isdir(real_target):
                shutil.rmtree(real_target)
                deleted = True
                break
        if not deleted:
            raise HTTPException(status_code=404, detail="目录不存在")
        return {"success": True, "message": f"已删除 {dir_name}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


# ==================== 六阶段流程 API ====================

@router.post("/courseware/analyze-requirements", tags=["课件-六阶段流程"])
async def analyze_requirements(
    topic: str = Body(..., description="课程主题"),
    audience: str = Body("大学生", description="目标受众"),
    duration: int = Body(45, description="课程时长（分钟）"),
    key_points: Optional[list] = Body(None, description="核心知识点"),
    reference_docs: Optional[list] = Body(None, description="参考文档"),
    subject: str = Body("general", description="学科类型")
):
    """阶段1：需求解析与课件定位 - 创建标准化课件需求说明书"""
    try:
        generator = CoursewareGenerator(output_dir=OUTPUT_DIR)

        requirements = generator.analyze_requirements(
            topic=topic,
            audience=audience,
            duration=duration,
            key_points=key_points,
            reference_docs=reference_docs,
            subject=subject
        )

        return {
            "success": True,
            "message": "需求解析成功",
            "requirements": requirements
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"需求解析失败: {str(e)}"
        }


@router.post("/courseware/generate-outline", tags=["课件-六阶段流程"])
async def generate_outline(
    request_data: dict = Body(..., description="请求数据")
):
    """阶段2：结构化大纲生成 - 创建层级清晰的PPT大纲"""
    try:
        generator = CoursewareGenerator(output_dir=OUTPUT_DIR)

        # 从请求数据中提取requirements
        requirements = request_data.get("requirements", request_data)
        outline = generator.generate_ppt_outline(requirements)

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


@router.post("/courseware/generate-detailed-content", tags=["课件-六阶段流程"])
async def generate_detailed_content(
    request_data: dict = Body(..., description="请求数据")
):
    """阶段3：分页面精细化内容生成 - 为每页PPT生成详细内容"""
    try:
        generator = CoursewareGenerator(output_dir=OUTPUT_DIR)

        # 从请求数据中提取outline和requirements
        outline = request_data.get("outline")
        requirements = request_data.get("requirements")
        
        if not outline or not requirements:
            return {
                "success": False,
                "message": "缺少必要的参数"
            }

        detailed_content = generator.generate_detailed_content(outline, requirements)

        return {
            "success": True,
            "message": "精细化内容生成成功",
            "detailed_content": detailed_content
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"精细化内容生成失败: {str(e)}"
        }


@router.post("/courseware/generate-visual-style", tags=["课件-六阶段流程"])
async def generate_visual_style(
    topic: str = Body(..., description="课程主题"),
    subject: str = Body("general", description="学科类型"),
    audience: str = Body("大学生", description="目标受众")
):
    """阶段4：PPT视觉与格式规范生成 - 创建配套的PPT样式规范"""
    try:
        generator = CoursewareGenerator(output_dir=OUTPUT_DIR)

        style = generator.generate_visual_style(topic, subject, audience)

        return {
            "success": True,
            "message": "视觉样式生成成功",
            "style": style
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"视觉样式生成失败: {str(e)}"
        }


@router.post("/courseware/generate-full", tags=["课件-六阶段流程"])
async def generate_full_courseware(
    topic: str = Body(..., description="课程主题"),
    audience: str = Body("大学生", description="目标受众"),
    duration: int = Body(45, description="课程时长（分钟）"),
    key_points: Optional[list] = Body(None, description="核心知识点"),
    reference_docs: Optional[list] = Body(None, description="参考文档"),
    subject: str = Body("general", description="学科类型"),
    provider: Optional[str] = Body(None, description="LLM提供商")
):
    """完整六阶段流程 - 从需求分析到PPT生成"""
    try:
        generator = CoursewareGenerator(output_dir=OUTPUT_DIR)

        # 阶段1：需求解析与课件定位
        requirements = generator.analyze_requirements(
            topic=topic,
            audience=audience,
            duration=duration,
            key_points=key_points,
            reference_docs=reference_docs,
            subject=subject
        )

        # 阶段2：结构化大纲生成
        outline = generator.generate_ppt_outline(requirements)

        # 阶段3：分页面精细化内容生成
        detailed_content = generator.generate_detailed_content(outline, requirements)

        # 阶段4：PPT视觉与格式规范生成
        style = generator.generate_visual_style(topic, subject, audience)

        # 生成最终课件
        result = generator.generate(
            topic=topic,
            duration=duration,
            audience=audience,
            format="PPT+Word",
            provider=provider,
            template="standard",
            subject=subject
        )

        return {
            "success": True,
            "message": "完整课件生成成功",
            "process": {
                "requirements": requirements,
                "outline": outline,
                "detailed_content": detailed_content,
                "style": style
            },
            "result": {
                "topic": result.get("topic"),
                "duration": result.get("duration"),
                "audience": result.get("audience"),
                "template": result.get("template"),
                "subject": result.get("subject"),
                "teaching_style": result.get("teaching_style"),
                "lesson_plan": result.get("lesson_plan"),
                "ppt_content": result.get("ppt_content"),
                "animation_ideas": result.get("animation_ideas"),
                "interactive_games": result.get("interactive_games"),
                "files": result.get("files", {}),
                "task_dir": result.get("task_dir")
            }
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"完整课件生成失败: {str(e)}"
        }
