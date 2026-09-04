"""PPT生成API接口 - 包含PPT生成、进度查询、在线预览、文件下载、PPT内容迭代修改"""
import os
import json
import sys
import subprocess
import tempfile
from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Body, Query
from fastapi.responses import FileResponse, JSONResponse
from typing import Optional, List, Dict, Tuple

from ..paths import GENERATED_CW, BACKEND_DIR
from ..services.ppt_content_generator import PPTContentGenerator
from ..services.teaching_compliance import run_compliance_gate
from ..services.llm_service import llm_service

# 设计思路参考：清华大学THU-MAIC/OpenMAIC开源项目，核心代码自主实现

router = APIRouter(prefix="/ppt", tags=["PPT"])

# 生成器实例（内容生成仍在主进程，文件生成用子进程隔离防崩溃）
ppt_content_generator = PPTContentGenerator()
# ppt_file_generator 改为按需在子进程中创建，避免主进程加载C扩展导致崩溃


def _generate_pptx_safe(ppt_content: Dict, task_dir: str = None) -> Optional[str]:
    """在子进程中安全生成PPTX文件，隔离C扩展崩溃（0xC0000005）对主进程的影响。
    增加重试机制：首次失败后尝试用不同方式重试一次。"""
    fd, data_path = tempfile.mkstemp(suffix='.json', prefix='ppt_gen_')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump({'content': ppt_content, 'task_dir': task_dir}, f, ensure_ascii=False)

        # 构造子进程脚本，使用正斜杠避免Windows路径转义问题
        backend_dir = str(BACKEND_DIR).replace('\\', '/')
        data_path_fwd = data_path.replace('\\', '/')

        # 两种子进程脚本：方式1用PPTFileGenerator，方式2用轻量pptx直接写
        scripts = [
            # 方式1：标准PPTFileGenerator（可能因C扩展崩溃）
            (
                f"import json,sys,os\n"
                f"sys.path.insert(0,r'{backend_dir}')\n"
                f"os.chdir(r'{backend_dir}')\n"
                f"with open(r'{data_path_fwd}','r',encoding='utf-8') as f:\n"
                f"    payload=json.load(f)\n"
                f"from app.services.ppt_file_generator import PPTFileGenerator\n"
                f"gen=PPTFileGenerator()\n"
                f"path=gen.generate_pptx(payload['content'],payload.get('task_dir'))\n"
                f"print(path or '__NONE__')\n"
            ),
            # 方式2：轻量方式（避免C扩展）
            (
                f"import json,sys,os,re,uuid\n"
                f"sys.path.insert(0,r'{backend_dir}')\n"
                f"os.chdir(r'{backend_dir}')\n"
                f"with open(r'{data_path_fwd}','r',encoding='utf-8') as f:\n"
                f"    payload=json.load(f)\n"
                f"from app.ppt_tasks import _build_detailed_content,_write_pptx,_theme_rgb\n"
                f"from app.paths import GENERATED_CW\n"
                f"content=payload['content']\n"
                f"meta=content.get('metadata',{{}})\n"
                f"topic=meta.get('topic','未命名课程')\n"
                f"audience=meta.get('audience','学生')\n"
                f"theme=meta.get('theme_color','蓝色系')\n"
                f"outline_data=content.get('outline',[])\n"
                f"outline_lines=[]\n"
                f"for p in outline_data:\n"
                f"    ct=p.get('core_topic','')\n"
                f"    co=p.get('content_outline',[])\n"
                f"    if isinstance(co,list) and co:\n"
                f"        outline_lines.append(ct)\n"
                f"        for item in co:\n"
                f"            outline_lines.append(f'  - {{item}}')\n"
                f"    else:\n"
                f"        outline_lines.append(ct)\n"
                f"outline_str='\\n'.join(outline_lines)\n"
                f"tid=content.get('task_id',uuid.uuid4().hex[:12])\n"
                f"safe_name=re.sub(r'[<>:\"/\\\\\\\\|?*]','_',topic[:36])+'_'+tid[:10]\n"
                f"fb_dir=GENERATED_CW/safe_name\n"
                f"fb_dir.mkdir(parents=True,exist_ok=True)\n"
                f"fname=re.sub(r'[<>:\"/\\\\\\\\|?*]','_',topic[:40] or 'courseware')+'.pptx'\n"
                f"fb_path=fb_dir/fname\n"
                f"fb_content=_build_detailed_content(topic,outline_str,audience)\n"
                f"_write_pptx(fb_path,topic,fb_content,theme)\n"
                f"print(str(fb_path))\n"
            ),
        ]

        for attempt, script in enumerate(scripts):
            try:
                result = subprocess.run(
                    [sys.executable, '-c', script],
                    capture_output=True, text=True, timeout=180,
                    cwd=str(BACKEND_DIR)
                )
                output = (result.stdout or '').strip()
                if result.returncode == 0 and output and output != '__NONE__':
                    if attempt > 0:
                        print(f"[PPT子进程] 方式{attempt+1}重试成功")
                    return output
                else:
                    err_info = (result.stderr or '')[:500]
                    print(f"[PPT子进程] 方式{attempt+1}生成失败 exitcode={result.returncode} stderr={err_info}")
            except subprocess.TimeoutExpired:
                print(f"[PPT子进程] 方式{attempt+1}生成超时(180s)")
            except Exception as e:
                print(f"[PPT子进程] 方式{attempt+1}异常: {e}")

        return None
    except Exception as e:
        print(f"[PPT子进程] 异常: {e}")
        return None
    finally:
        try:
            os.unlink(data_path)
        except Exception:
            pass

# 生成任务状态存储
generation_tasks = {}

# 课件输出目录（与 app.paths 一致）
COURSEWARE_OUTPUT_DIR = str(GENERATED_CW)


def _find_pptx_on_disk(task_id: str = None, task_dir: str = None, topic: str = None) -> Tuple[Optional[str], Optional[str]]:
    """在文件系统中查找PPTX文件（当内存中找不到任务时的回退方案）
    
    Returns:
        (pptx_path, task_dir) 或 (None, None)
    """
    # Tier 1: 通过 task_dir 直接查找
    if task_dir and os.path.isdir(task_dir):
        for f in os.listdir(task_dir):
            if f.endswith('.pptx'):
                pptx_path = os.path.join(task_dir, f)
                # 安全检查
                real_path = os.path.realpath(pptx_path)
                if os.path.exists(real_path):
                    return (real_path, task_dir)
    
    # Tier 2: 通过 task_id 在 ppt_data.json 中查找
    if task_id and os.path.isdir(COURSEWARE_OUTPUT_DIR):
        for dirname in sorted(os.listdir(COURSEWARE_OUTPUT_DIR), reverse=True):
            dir_path = os.path.join(COURSEWARE_OUTPUT_DIR, dirname)
            if not os.path.isdir(dir_path):
                continue
            data_path = os.path.join(dir_path, "ppt_data.json")
            if os.path.exists(data_path):
                try:
                    with open(data_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if data.get("task_id") == task_id:
                        for fn in os.listdir(dir_path):
                            if fn.endswith('.pptx'):
                                return (os.path.join(dir_path, fn), dir_path)
                except Exception:
                    pass
    
    # Tier 3: 通过 topic 名称匹配最新的目录
    if topic and os.path.isdir(COURSEWARE_OUTPUT_DIR):
        clean_topic = topic.replace('/', '_').replace('\\', '_').replace(':', '_').replace('*', '_')
        for dirname in sorted(os.listdir(COURSEWARE_OUTPUT_DIR), reverse=True):
            if clean_topic in dirname:
                dir_path = os.path.join(COURSEWARE_OUTPUT_DIR, dirname)
                if os.path.isdir(dir_path):
                    for fn in os.listdir(dir_path):
                        if fn.endswith('.pptx'):
                            return (os.path.join(dir_path, fn), dir_path)
    
    return (None, None)


def _find_ppt_data_on_disk(task_id: str = None, task_dir: str = None, topic: str = None) -> Optional[str]:
    """在文件系统中查找 ppt_data.json 文件
    
    Returns:
        ppt_data.json 的路径，或 None
    """
    # Tier 1: 通过 task_dir 直接查找
    if task_dir and os.path.isdir(task_dir):
        data_path = os.path.join(task_dir, "ppt_data.json")
        if os.path.exists(data_path):
            return data_path
    
    # Tier 2: 通过 task_id 查找
    if task_id and os.path.isdir(COURSEWARE_OUTPUT_DIR):
        for dirname in sorted(os.listdir(COURSEWARE_OUTPUT_DIR), reverse=True):
            dir_path = os.path.join(COURSEWARE_OUTPUT_DIR, dirname)
            if not os.path.isdir(dir_path):
                continue
            data_path = os.path.join(dir_path, "ppt_data.json")
            if os.path.exists(data_path):
                try:
                    with open(data_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if data.get("task_id") == task_id:
                        return data_path
                except Exception:
                    pass
    
    # Tier 3: 通过 topic 匹配
    if topic and os.path.isdir(COURSEWARE_OUTPUT_DIR):
        clean_topic = topic.replace('/', '_').replace('\\', '_').replace(':', '_').replace('*', '_')
        for dirname in sorted(os.listdir(COURSEWARE_OUTPUT_DIR), reverse=True):
            if clean_topic in dirname:
                dir_path = os.path.join(COURSEWARE_OUTPUT_DIR, dirname)
                if os.path.isdir(dir_path):
                    data_path = os.path.join(dir_path, "ppt_data.json")
                    if os.path.exists(data_path):
                        return data_path
    
    return None

class PPTGenerationTask:
    """PPT生成任务类"""
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.status = "pending"
        self.progress = 0
        self.result = None
        self.error = None

@router.post("/generate")
async def generate_ppt(
    background_tasks: BackgroundTasks,
    topic: str = Body(...),
    duration: int = Body(...),
    audience: str = Body(...),
    subject: str = Body(default="general"),
    theme_color: str = Body(default="蓝色系"),
    style_preference: str = Body(default="专业严谨"),
    key_points: Optional[List[str]] = Body(default=None),
    reference_docs: Optional[List[str]] = Body(default=None),
    template: str = Body(default="standard"),
):
    """生成PPT"""
    import uuid
    task_id = str(uuid.uuid4())
    task = PPTGenerationTask(task_id)
    task.status = "initializing"
    task.progress = 0
    generation_tasks[task_id] = task
    
    # 启动后台任务
    background_tasks.add_task(
        _generate_ppt_task,
        task_id,
        topic,
        duration,
        audience,
        subject,
        theme_color,
        style_preference,
        key_points or [],
        reference_docs or [],
        template
    )
    
    return {
        "success": True,
        "message": "PPT生成任务已启动，正在准备生成...",
        "task_id": task_id,
        "estimated_time": f"约{duration//5 + 2}分钟"
    }

async def _generate_ppt_task(task_id: str, topic: str, duration: int, audience: str, subject: str, theme_color: str, style_preference: str, key_points: list, reference_docs: list, template: str):
    """PPT生成后台任务"""
    task = generation_tasks.get(task_id)
    if not task:
        return
    
    try:
        task.status = "generating"
        task.progress = 0
        
        # 1. 分析需求和生成大纲
        task.progress = 10
        ctx = ppt_content_generator.prepare_teaching_context(
            topic, duration, audience, subject, key_points or [], reference_docs or []
        )
        key_points_eff = ctx.get("key_points") or []
        teaching_content = ctx.get("teaching_content") or ""
        expansion = ctx.get("expansion") or {}
        
        task.progress = 20
        teaching_goals = ppt_content_generator._define_teaching_goals(topic, audience, subject, key_points_eff, teaching_content)
        
        task.progress = 30
        outline = ppt_content_generator.generate_ppt_outline(
            topic, duration, audience, subject, key_points_eff, teaching_content, expansion=expansion
        )
        
        # 2. 生成视觉风格
        task.progress = 40
        visual_style = ppt_content_generator.generate_visual_style(topic, audience, duration, subject, theme_color, style_preference)
        
        # 3. 生成详细内容
        task.progress = 50
        detailed_content = ppt_content_generator.generate_detailed_content(
            outline, topic, duration, audience, subject, key_points_eff, teaching_content
        )
        
        # 3.5 AI生成图片搜索关键词(用于自动配图)
        task.progress = 55
        try:
            from ..services.image_service import image_service
            detailed_content = image_service.generate_image_queries(detailed_content, topic, subject)
        except Exception as e:
            print(f"生成图片关键词失败(不影响PPT生成): {e}")
        
        task.progress = 60
        ppt_content = {
            "outline": outline,
            "visual_style": visual_style,
            "detailed_content": detailed_content,
            "metadata": {
                "topic": topic,
                "duration": duration,
                "audience": audience,
                "subject": subject,
                "theme_color": theme_color,
                "style_preference": style_preference,
                "key_points": key_points_eff,
                "teaching_content": teaching_content,
                "topic_expansion": expansion,
                "reference_docs": reference_docs,
                "template": template
            }
        }
        
        # 4. 生成PPT文件（子进程隔离，防止C扩展崩溃拖垮主服务）
        task.progress = 70
        pptx_path = _generate_pptx_safe(ppt_content)
        if not pptx_path:
            # 子进程生成失败，尝试在进程中用轻量级方式生成
            print(f"[PPT任务] 子进程生成PPTX失败，使用进程内轻量生成作为回退")
            try:
                from ..ppt_tasks import TASKS as _pt_tasks, _write_pptx, _build_detailed_content, _theme_rgb
                import re as _re
                safe_name = _re.sub(r'[<>:"/\\|?*]', "_", topic[:36]) + "_" + task_id[:10]
                fallback_dir = GENERATED_CW / safe_name
                fallback_dir.mkdir(parents=True, exist_ok=True)
                fname = _re.sub(r'[<>:"/\\|?*]', "_", topic[:40] or "courseware") + ".pptx"
                fb_path = fallback_dir / fname

                # 优先使用 LLM 已生成的大纲（包含详细 core_topic 和 content_outline）
                # 而不是仅传递 core_topic 列表
                outline_lines = []
                for p in outline:
                    ct = p.get("core_topic", "")
                    co = p.get("content_outline", [])
                    if isinstance(co, list) and co:
                        outline_lines.append(ct)
                        for item in co:
                            outline_lines.append(f"  - {item}")
                    else:
                        outline_lines.append(ct)

                outline_str = "\n".join(outline_lines) if outline_lines else json.dumps(
                    [p.get("core_topic", "") for p in outline], ensure_ascii=False
                )
                fallback_content = _build_detailed_content(topic, outline_str, audience)
                _write_pptx(fb_path, topic, fallback_content, theme_color)
                pptx_path = str(fb_path)
                print(f"[PPT任务] 轻量回退生成成功: {pptx_path}")
            except Exception as fb_err:
                print(f"[PPT任务] 轻量回退也失败: {fb_err}")
                pptx_path = None

        if not pptx_path:
            raise RuntimeError("PPTX文件生成失败（子进程与进程内回退均失败），请检查python-pptx/lxml依赖或尝试更换主题")
        
        # 5. 保存生成数据（包含task_id以便文件系统回退查找）
        task.progress = 90
        task_dir = os.path.dirname(pptx_path)
        ppt_content["task_id"] = task_id
        data_path = os.path.join(task_dir, "ppt_data.json")
        with open(data_path, 'w', encoding='utf-8') as f:
            json.dump(ppt_content, f, ensure_ascii=False, indent=2)
        
        task.progress = 100
        task.status = "completed"
        task.result = {
            "task_id": task_id,
            "pptx_path": pptx_path,
            "task_dir": task_dir,
            "topic": topic,
            "duration": duration,
            "audience": audience,
            "subject": subject,
            "theme_color": theme_color,
            "style_preference": style_preference,
            "key_points": key_points_eff,
            "reference_docs": reference_docs,
            "template": template,
            "files": {
                "pptx": os.path.basename(pptx_path)
            },
            "ppt_content": ppt_content
        }

        # 出厂质检闸门：纯规则离线扫描，只报告不阻断。
        # outline 是页列表（每项一个 core_topic），故其长度即真实页数，
        # 比从正文正则猜『第N页』可靠。
        _outline = ppt_content.get("outline")
        task.result["compliance"] = run_compliance_gate(
            "ppt",
            ppt_content,
            {
                "level": audience,
                "subject": subject,
                "topic": topic,
                "duration": duration,
                "page_count": len(_outline) if isinstance(_outline, list) else None,
            },
        )
        
    except Exception as e:
        task.status = "failed"
        task.error = str(e)
        print(f"PPT生成失败: {e}")

@router.get("/status/{task_id}")
async def get_ppt_generation_status(task_id: str):
    """获取PPT生成进度"""
    task = generation_tasks.get(task_id)
    if not task:
        # 内存中找不到任务时，检查文件系统是否已有生成结果
        pptx_path, found_dir = _find_pptx_on_disk(task_id=task_id)
        if pptx_path:
            return {
                "success": True,
                "task_id": task_id,
                "status": "completed",
                "progress": 100,
                "current_step": "任务完成",
                "result": {
                    "task_id": task_id,
                    "pptx_path": pptx_path,
                    "task_dir": found_dir,
                    "files": {"pptx": os.path.basename(pptx_path)}
                },
                "error": None
            }
        # 任务确实不存在，返回unknown状态而非404（避免前端轮询崩溃）
        return {
            "success": True,
            "task_id": task_id,
            "status": "unknown",
            "progress": 0,
            "current_step": "任务不存在或已过期",
            "result": None,
            "error": "任务不存在，可能已过期或服务已重启"
        }
    
    # 根据进度返回当前正在执行的步骤
    current_step = ""
    if task.progress < 10:
        current_step = "初始化任务"
    elif task.progress < 30:
        current_step = "分析需求和生成大纲"
    elif task.progress < 40:
        current_step = "生成视觉风格"
    elif task.progress < 55:
        current_step = "生成详细内容"
    elif task.progress < 60:
        current_step = "AI智能配图"
    elif task.progress < 70:
        current_step = "准备生成PPT文件"
    elif task.progress < 90:
        current_step = "生成PPT文件并插入配图"
    elif task.progress < 100:
        current_step = "保存生成数据"
    else:
        current_step = "任务完成"
    
    return {
        "success": True,
        "task_id": task_id,
        "status": task.status,
        "progress": task.progress,
        "current_step": current_step,
        "result": task.result,
        "error": task.error
    }

@router.get("/preview/{task_id}")
async def preview_ppt(task_id: str, task_dir: Optional[str] = Query(None), topic: Optional[str] = Query(None)):
    """在线预览PPT"""
    task = generation_tasks.get(task_id)
    
    # 确定 ppt_data.json 的路径
    ppt_data_path = None
    
    if task and task.status == "completed" and task.result:
        td = task.result.get("task_dir")
        if td:
            ppt_data_path = os.path.join(td, "ppt_data.json")
    
    # 内存中找不到或路径无效，使用文件系统回退
    if not ppt_data_path or not os.path.exists(ppt_data_path):
        ppt_data_path = _find_ppt_data_on_disk(task_id=task_id, task_dir=task_dir, topic=topic)
    
    if not ppt_data_path or not os.path.exists(ppt_data_path):
        raise HTTPException(status_code=404, detail="PPT数据文件不存在，任务可能已过期")
    
    try:
        with open(ppt_data_path, 'r', encoding='utf-8') as f:
            ppt_data = json.load(f)
        
        return {
            "success": True,
            "task_id": task_id,
            "ppt_data": ppt_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取PPT数据失败: {str(e)}")

@router.get("/download/{task_id}")
async def download_ppt(task_id: str, task_dir: Optional[str] = Query(None), topic: Optional[str] = Query(None)):
    """下载PPT文件"""
    pptx_path = None
    
    # 优先从内存中查找
    task = generation_tasks.get(task_id)
    if task and task.status == "completed" and task.result:
        pptx_path = task.result.get("pptx_path")
    
    # 内存中找不到或文件不存在，使用文件系统回退
    if not pptx_path or not os.path.exists(pptx_path):
        pptx_path, _ = _find_pptx_on_disk(task_id=task_id, task_dir=task_dir, topic=topic)
    
    if not pptx_path or not os.path.exists(pptx_path):
        raise HTTPException(status_code=404, detail="PPT文件不存在，任务可能已过期，请重新生成")
    
    return FileResponse(
        path=pptx_path,
        filename=os.path.basename(pptx_path),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )

@router.post("/modify/{task_id}")
async def modify_ppt(
    task_id: str,
    modifications: Dict,
    background_tasks: BackgroundTasks = None
):
    """PPT内容迭代修改"""
    task = generation_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if task.status != "completed" or not task.result:
        raise HTTPException(status_code=400, detail="PPT尚未生成完成")
    
    task_dir = task.result.get("task_dir")
    if not task_dir:
        raise HTTPException(status_code=400, detail="任务目录不存在")
    
    # 读取原始PPT数据
    ppt_data_path = os.path.join(task_dir, "ppt_data.json")
    if not os.path.exists(ppt_data_path):
        raise HTTPException(status_code=400, detail="PPT数据文件不存在")
    
    try:
        with open(ppt_data_path, 'r', encoding='utf-8') as f:
            ppt_data = json.load(f)
        
        # 应用修改
        modified_ppt_data = _apply_modifications(ppt_data, modifications)
        
        # 生成新的PPT文件
        new_task_id = f"{task_id}_modified"
        generation_tasks[new_task_id] = PPTGenerationTask(new_task_id)
        
        background_tasks.add_task(
            _generate_modified_ppt_task,
            new_task_id,
            modified_ppt_data,
            task_dir
        )
        
        return {
            "success": True,
            "message": "PPT修改任务已启动",
            "task_id": new_task_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"修改PPT失败: {str(e)}")

async def _generate_modified_ppt_task(task_id: str, modified_ppt_data: Dict, task_dir: str):
    """生成修改后的PPT"""
    task = generation_tasks.get(task_id)
    if not task:
        return
    
    try:
        task.status = "generating"
        task.progress = 50
        
        # 生成修改后的PPT文件（子进程隔离）
        pptx_path = _generate_pptx_safe(modified_ppt_data, task_dir)
        
        task.progress = 100
        task.status = "completed"
        task.result = {
            "pptx_path": pptx_path,
            "task_dir": task_dir
        }
        
    except Exception as e:
        task.status = "failed"
        task.error = str(e)
        print(f"生成修改后的PPT失败: {e}")

@router.post("/analyze-requirements")
async def analyze_ppt_requirements(
    topic: str = Body(...),
    audience: str = Body(...),
    duration: int = Body(...),
    key_points: Optional[List[str]] = Body(default=None),
    reference_docs: Optional[List[str]] = Body(default=None),
    subject: str = Body(default="general")
):
    """分析PPT需求"""
    try:
        ctx = ppt_content_generator.prepare_teaching_context(
            topic, duration, audience, subject, key_points or [], reference_docs or []
        )
        outline = ppt_content_generator.generate_ppt_outline(
            topic,
            duration,
            audience,
            subject,
            ctx.get("key_points") or [],
            ctx.get("teaching_content") or "",
            expansion=ctx.get("expansion") or {},
        )
        
        # 分析需求
        requirements = {
            "basic_info": {
                "topic": topic,
                "audience": audience,
                "duration": duration,
                "subject": subject,
                "key_points": key_points or [],
                "reference_docs": reference_docs or []
            },
            "outline": outline,
            "page_count": len(outline),
            "recommended_slide_time": round(duration / max(len(outline), 1), 1)
        }
        
        return {
            "success": True,
            "requirements": requirements
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"分析需求失败: {str(e)}"
        }

@router.post("/generate-outline")
async def generate_ppt_outline(
    requirements: Dict = Body(...)
):
    """生成PPT大纲"""
    try:
        # 提取需求信息
        topic = requirements.get("topic", requirements.get("basic_info", {}).get("topic", "未命名课程"))
        audience = requirements.get("audience", requirements.get("basic_info", {}).get("audience", "大学生"))
        duration = requirements.get("duration", requirements.get("basic_info", {}).get("duration", 45))
        subject = requirements.get("subject", requirements.get("basic_info", {}).get("subject", "general"))
        key_points = requirements.get("key_points", requirements.get("basic_info", {}).get("key_points", []))
        reference_docs = requirements.get("reference_docs", requirements.get("basic_info", {}).get("reference_docs", []))

        ctx = ppt_content_generator.prepare_teaching_context(
            topic, duration, audience, subject, key_points or [], reference_docs or []
        )
        outline = ppt_content_generator.generate_ppt_outline(
            topic,
            duration,
            audience,
            subject,
            ctx.get("key_points") or [],
            ctx.get("teaching_content") or "",
            expansion=ctx.get("expansion") or {},
        )
        
        return {
            "success": True,
            "outline": outline
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"生成大纲失败: {str(e)}"
        }

@router.post("/generate-detailed-content")
async def generate_ppt_detailed_content(
    outline: List[Dict] = Body(...),
    requirements: Dict = Body(...)
):
    """生成PPT详细内容"""
    try:
        # 提取需求信息
        topic = requirements.get("topic", requirements.get("basic_info", {}).get("topic", "未命名课程"))
        audience = requirements.get("audience", requirements.get("basic_info", {}).get("audience", "大学生"))
        duration = requirements.get("duration", requirements.get("basic_info", {}).get("duration", 45))
        subject = requirements.get("subject", requirements.get("basic_info", {}).get("subject", "general"))
        key_points = requirements.get("key_points", requirements.get("basic_info", {}).get("key_points", []))
        reference_docs = requirements.get("reference_docs", requirements.get("basic_info", {}).get("reference_docs", []))

        ctx = ppt_content_generator.prepare_teaching_context(
            topic, duration, audience, subject, key_points or [], reference_docs or []
        )
        detailed_content = ppt_content_generator.generate_detailed_content(
            outline,
            topic,
            duration,
            audience,
            subject,
            ctx.get("key_points") or [],
            ctx.get("teaching_content") or "",
        )
        
        return {
            "success": True,
            "detailed_content": detailed_content
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"生成详细内容失败: {str(e)}"
        }

@router.post("/generate-visual-style")
async def generate_ppt_visual_style(
    topic: str = Body(...),
    subject: str = Body(default="general"),
    audience: str = Body(default="大学生"),
    theme_color: str = Body(default="蓝色系"),
    style_preference: str = Body(default="专业严谨")
):
    """生成PPT视觉风格"""
    try:
        # 生成视觉风格
        visual_style = ppt_content_generator.generate_visual_style(
            topic, audience, 45, subject, theme_color, style_preference
        )
        
        return {
            "success": True,
            "visual_style": visual_style
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"生成视觉风格失败: {str(e)}"
        }

def _apply_modifications(ppt_data: Dict, modifications: Dict) -> Dict:
    """应用PPT修改"""
    # 深度复制数据
    import copy
    modified_data = copy.deepcopy(ppt_data)
    
    # 应用修改
    if "metadata" in modifications:
        modified_data["metadata"].update(modifications["metadata"])
    
    if "detailed_content" in modifications:
        for i, page_modification in enumerate(modifications["detailed_content"]):
            if i < len(modified_data["detailed_content"]):
                modified_data["detailed_content"][i].update(page_modification)
    
    return modified_data

@router.get("/download")
async def download_ppt_by_path(path: str):
    """根据文件路径下载PPT文件"""
    try:
        # 安全检查：确保路径在generated_courseware目录下
        if not path.startswith("generated_courseware"):
            raise HTTPException(status_code=403, detail="路径无效")
        
        # 构建绝对路径
        pptx_path = os.path.join(os.getcwd(), path)
        
        # 防止路径遍历攻击
        allowed_dir = os.path.realpath(os.path.join(os.getcwd(), "generated_courseware"))
        real_path = os.path.realpath(pptx_path)
        if not real_path.startswith(allowed_dir):
            raise HTTPException(status_code=403, detail="路径无效")
        
        if not os.path.exists(real_path):
            raise HTTPException(status_code=404, detail="PPT文件不存在")
        
        return FileResponse(
            path=real_path,
            filename=os.path.basename(pptx_path),
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"下载PPT失败: {str(e)}")
        raise HTTPException(status_code=500, detail="下载失败")


# ==================== 迭代优化与版本管理 ====================

def _save_version(task_dir: str, ppt_data: Dict, description: str) -> int:
    """保存PPT版本快照"""
    from datetime import datetime
    versions_path = os.path.join(task_dir, "versions.json")
    
    # 读取已有版本
    versions = []
    if os.path.exists(versions_path):
        try:
            with open(versions_path, 'r', encoding='utf-8') as f:
                versions = json.load(f)
        except Exception:
            versions = []
    
    # 新版本号
    version_number = len(versions) + 1
    
    # 保存版本快照
    versions.append({
        "version": version_number,
        "timestamp": datetime.now().isoformat(),
        "description": description,
        "ppt_data_snapshot": ppt_data
    })
    
    with open(versions_path, 'w', encoding='utf-8') as f:
        json.dump(versions, f, ensure_ascii=False, indent=2)
    
    return version_number


def _find_task_dir(task_id: str) -> Optional[str]:
    """查找任务目录"""
    # 先从内存任务中查找
    task = generation_tasks.get(task_id)
    if task and task.result:
        task_dir = task.result.get("task_dir")
        if task_dir and os.path.exists(task_dir):
            return task_dir
    
    # 在文件系统中查找
    _, task_dir = _find_pptx_on_disk(task_id=task_id)
    if task_dir:
        return task_dir
    
    return None


@router.post("/refine/{task_id}")
async def refine_ppt(
    task_id: str,
    feedback: str = Body(..., description="自然语言修改意见"),
    modification_type: str = Body("content", description="修改类型"),
    target_page: Optional[int] = Body(None, description="目标页码(从0开始)")
):
    """LLM驱动的PPT智能优化"""
    # 查找任务目录
    task_dir = _find_task_dir(task_id)
    if not task_dir:
        raise HTTPException(status_code=404, detail="任务不存在或目录丢失")
    
    # 加载ppt_data
    ppt_data_path = os.path.join(task_dir, "ppt_data.json")
    if not os.path.exists(ppt_data_path):
        raise HTTPException(status_code=404, detail="PPT数据文件不存在")
    
    try:
        with open(ppt_data_path, 'r', encoding='utf-8') as f:
            ppt_data = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取PPT数据失败: {e}")
    
    # 保存当前版本
    version_number = _save_version(task_dir, ppt_data, f"修改前备份: {feedback[:50]}")
    
    # 提取当前内容
    detailed_content = ppt_data.get("detailed_content", [])
    if not detailed_content:
        raise HTTPException(status_code=400, detail="PPT内容为空")
    
    # 构建LLM修改prompt
    target_info = ""
    if target_page is not None and 0 <= target_page < len(detailed_content):
        target_info = f"\n重点修改第{target_page + 1}页(索引{target_page})的内容。"
    
    content_json = json.dumps(detailed_content, ensure_ascii=False, indent=2)
    # 截断过长的内容避免超出token限制
    if len(content_json) > 6000:
        content_json = content_json[:6000] + "\n... (内容过长已截断)"
    
    prompt = f"""你是一个PPT内容优化专家。请根据用户的修改意见修改以下PPT内容。

当前PPT内容(JSON数组):
{content_json}

修改意见: {feedback}
修改类型: {modification_type}
{target_info}

要求:
1. 只修改需要修改的部分，保持其他内容不变
2. 保持JSON数组格式，每个元素代表一页
3. 每页必须保留page_num, page_type, core_topic字段
4. 只输出修改后的完整JSON数组，不要其他说明文字

输出格式: [{{...}}, {{...}}, ...]"""
    
    try:
        response = llm_service.chat(prompt)
        
        # 解析LLM输出
        import re as re_module
        json_match = re_module.search(r'\[.*\]', response, re_module.DOTALL)
        if json_match:
            new_content = json.loads(json_match.group())
            if isinstance(new_content, list) and len(new_content) > 0:
                ppt_data["detailed_content"] = new_content
            else:
                raise ValueError("LLM返回的内容格式无效")
        else:
            raise ValueError("无法从LLM输出中提取JSON数组")
        
        # 保存修改后的数据
        with open(ppt_data_path, 'w', encoding='utf-8') as f:
            json.dump(ppt_data, f, ensure_ascii=False, indent=2)
        
        # 尝试重新生成PPTX文件
        try:
            pptx_path = _generate_pptx_safe(ppt_data, task_dir)
            if pptx_path:
                print(f"PPT重新生成成功: {pptx_path}")
        except Exception as e:
            print(f"重新生成PPTX文件失败: {e}")
        
        return {
            "success": True,
            "message": "PPT内容已优化",
            "version_number": version_number + 1,
            "detailed_content": ppt_data["detailed_content"]
        }
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="LLM输出解析失败，PPT内容未修改")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PPT优化失败: {str(e)}")


@router.get("/versions/{task_id}")
async def get_versions(task_id: str):
    """获取PPT版本历史"""
    task_dir = _find_task_dir(task_id)
    if not task_dir:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    versions_path = os.path.join(task_dir, "versions.json")
    if not os.path.exists(versions_path):
        return {"success": True, "versions": []}
    
    try:
        with open(versions_path, 'r', encoding='utf-8') as f:
            versions = json.load(f)
        
        # 返回版本列表（不包含完整快照数据，减少传输量）
        version_list = [{
            "version": v["version"],
            "timestamp": v["timestamp"],
            "description": v["description"]
        } for v in versions]
        
        return {"success": True, "versions": version_list}
    except Exception as e:
        return {"success": False, "message": str(e), "versions": []}


@router.post("/revert/{task_id}")
async def revert_ppt(
    task_id: str,
    version: int = Body(..., description="要恢复的版本号")
):
    """恢复PPT到指定版本"""
    task_dir = _find_task_dir(task_id)
    if not task_dir:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    versions_path = os.path.join(task_dir, "versions.json")
    if not os.path.exists(versions_path):
        raise HTTPException(status_code=404, detail="无版本历史")
    
    try:
        with open(versions_path, 'r', encoding='utf-8') as f:
            versions = json.load(f)
        
        # 查找目标版本
        target_version = None
        for v in versions:
            if v["version"] == version:
                target_version = v
                break
        
        if not target_version:
            raise HTTPException(status_code=404, detail=f"版本{version}不存在")
        
        ppt_data = target_version["ppt_data_snapshot"]
        
        # 覆盖当前ppt_data.json
        ppt_data_path = os.path.join(task_dir, "ppt_data.json")
        with open(ppt_data_path, 'w', encoding='utf-8') as f:
            json.dump(ppt_data, f, ensure_ascii=False, indent=2)
        
        # 重新生成PPTX
        try:
            pptx_path = _generate_pptx_safe(ppt_data, task_dir)
            if pptx_path:
                print(f"PPT重新生成成功: {pptx_path}")
        except Exception as e:
            print(f"重新生成PPTX文件失败: {e}")

        return {
            "success": True,
            "message": f"已恢复到版本{version}",
            "detailed_content": ppt_data.get("detailed_content", [])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"版本恢复失败: {str(e)}")
