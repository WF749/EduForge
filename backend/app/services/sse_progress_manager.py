# -*- coding: utf-8 -*-
"""
SSE进度管理器 - 实现生成过程的实时进度推送
基于FastAPI和SSE(Server-Sent Events)技术

功能：
1. 任务状态管理 - 创建、查询、更新、取消任务
2. 进度推送 - 通过SSE实时推送生成进度
3. 异常处理 - 推送错误信息并支持重试
4. 多任务支持 - 支持并行执行多个生成任务

使用方法：
1. 创建任务：sse_manager.create_task(task_type, params)
2. 启动任务：asyncio.create_task(sse_manager.run_task(task_id, generator_func))
3. 前端连接：GET /api/courseware/sse/{task_id}

Author: Matrix Agent
"""

import asyncio
import json
import uuid
import traceback
from typing import Dict, Optional, Any, Callable, List
from datetime import datetime
from collections import defaultdict
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

# SSE路由
router = APIRouter()

# ==================== 任务状态定义 ====================
class TaskStatus:
    """任务状态枚举"""
    PENDING = "pending"      # 等待中
    RUNNING = "running"      # 运行中
    PAUSED = "paused"       # 已暂停
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"       # 失败
    CANCELLED = "cancelled" # 已取消


# ==================== 进度阶段定义 ====================
class GenerationStage:
    """生成阶段枚举"""
    # 通用阶段
    INIT = "init"                    # 初始化
    REQUIREMENTS_PARSING = "requirements_parsing"  # 需求解析
    OUTLINE_GENERATION = "outline_generation"     # 大纲生成
    CONTENT_GENERATION = "content_generation"     # 内容生成
    STYLE_RENDERING = "style_rendering"           # 样式渲染
    FILE_GENERATION = "file_generation"           # 文件生成
    VALIDATION = "validation"                     # 校验
    COMPLETED = "completed"                       # 完成
    
    # 阶段名称映射（中文）
    STAGE_NAMES = {
        INIT: "初始化",
        REQUIREMENTS_PARSING: "需求解析",
        OUTLINE_GENERATION: "大纲生成",
        CONTENT_GENERATION: "内容生成",
        STYLE_RENDERING: "样式渲染",
        FILE_GENERATION: "文件生成",
        VALIDATION: "校验",
        COMPLETED: "完成"
    }
    
    # 阶段描述映射
    STAGE_DESCRIPTIONS = {
        INIT: "正在初始化生成环境...",
        REQUIREMENTS_PARSING: "正在解析用户需求...",
        OUTLINE_GENERATION: "正在生成课程大纲...",
        CONTENT_GENERATION: "正在生成详细内容...",
        STYLE_RENDERING: "正在应用视觉样式...",
        FILE_GENERATION: "正在生成文件...",
        VALIDATION: "正在校验文件完整性...",
        COMPLETED: "生成完成！"
    }


# ==================== SSE消息类 ====================
class SSEMessage:
    """SSE消息构建器"""
    
    @staticmethod
    def format_message(data: Dict[str, Any]) -> str:
        """
        格式化SSE消息
        格式: data: {json}\n\n
        """
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    
    @staticmethod
    def progress(
        stage: str,
        progress: float,
        message: str,
        preview_data: Optional[Dict] = None,
        stage_progress: Optional[float] = None,
        **kwargs
    ) -> str:
        """
        构建进度消息
        
        Args:
            stage: 当前阶段
            progress: 总体进度 (0-100)
            message: 状态文案
            preview_data: 预览数据
            stage_progress: 当前阶段进度 (0-100)
            **kwargs: 其他数据
        """
        data = {
            "type": "progress",
            "stage": stage,
            "stage_name": GenerationStage.STAGE_NAMES.get(stage, stage),
            "stage_description": GenerationStage.STAGE_DESCRIPTIONS.get(stage, ""),
            "progress": round(progress, 1),
            "message": message,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        
        if preview_data is not None:
            data["preview_data"] = preview_data
        
        if stage_progress is not None:
            data["stage_progress"] = round(stage_progress, 1)
        
        return SSEMessage.format_message(data)
    
    @staticmethod
    def stage_start(stage: str, message: str = "") -> str:
        """阶段开始消息"""
        data = {
            "type": "stage_start",
            "stage": stage,
            "stage_name": GenerationStage.STAGE_NAMES.get(stage, stage),
            "message": message or GenerationStage.STAGE_DESCRIPTIONS.get(stage, f"开始{stage}"),
            "timestamp": datetime.now().isoformat()
        }
        return SSEMessage.format_message(data)
    
    @staticmethod
    def stage_complete(stage: str, result: Any = None) -> str:
        """阶段完成消息"""
        data = {
            "type": "stage_complete",
            "stage": stage,
            "stage_name": GenerationStage.STAGE_NAMES.get(stage, stage),
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
        return SSEMessage.format_message(data)
    
    @staticmethod
    def preview_update(page_index: int, page_data: Dict) -> str:
        """预览更新消息"""
        data = {
            "type": "preview_update",
            "page_index": page_index,
            "page_data": page_data,
            "timestamp": datetime.now().isoformat()
        }
        return SSEMessage.format_message(data)
    
    @staticmethod
    def error(error_message: str, error_details: str = "", stage: str = "") -> str:
        """错误消息"""
        data = {
            "type": "error",
            "error": error_message,
            "error_details": error_details,
            "stage": stage,
            "timestamp": datetime.now().isoformat()
        }
        return SSEMessage.format_message(data)
    
    @staticmethod
    def completed(result: Dict) -> str:
        """完成消息"""
        data = {
            "type": "completed",
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
        return SSEMessage.format_message(data)
    
    @staticmethod
    def heartbeat() -> str:
        """心跳消息（保持连接）"""
        return SSEMessage.format_message({
            "type": "heartbeat",
            "timestamp": datetime.now().isoformat()
        })
    
    @staticmethod
    def done() -> str:
        """结束消息"""
        return "data: [DONE]\n\n"


# ==================== 任务信息类 ====================
class TaskInfo:
    """任务信息"""
    
    def __init__(self, task_id: str, task_type: str, params: Dict):
        self.task_id = task_id
        self.task_type = task_type
        self.params = params
        self.status = TaskStatus.PENDING
        self.progress = 0.0
        self.stage = GenerationStage.INIT
        self.message = "准备开始..."
        self.result = None
        self.error = None
        self.preview_data = {}
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.completed_at = None
        self._cancel_event = asyncio.Event()
        self._pause_event = asyncio.Event()
        self._queue: asyncio.Queue = asyncio.Queue()
        self._subscribers: List[asyncio.Queue] = []
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "params": self.params,
            "status": self.status,
            "progress": self.progress,
            "stage": self.stage,
            "stage_name": GenerationStage.STAGE_NAMES.get(self.stage, self.stage),
            "message": self.message,
            "result": self.result,
            "error": self.error,
            "preview_data": self.preview_data,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }
    
    def is_cancelled(self) -> bool:
        """检查是否已取消"""
        return self._cancel_event.is_set()
    
    def is_paused(self) -> bool:
        """检查是否已暂停"""
        return self._pause_event.is_set()
    
    def cancel(self):
        """取消任务"""
        self._cancel_event.set()
        self.status = TaskStatus.CANCELLED
    
    def pause(self):
        """暂停任务"""
        self._pause_event.set()
        self.status = TaskStatus.PAUSED
    
    def resume(self):
        """恢复任务"""
        self._pause_event.clear()
        self.status = TaskStatus.RUNNING


# ==================== SSE进度管理器 ====================
class SSEProgressManager:
    """
    SSE进度管理器
    
    使用示例:
    ```python
    # 1. 创建任务
    task_id = sse_manager.create_task("ppt", {"topic": "Python基础", "duration": 45})
    
    # 2. 在后台运行生成任务
    async def generate_ppt(task_id):
        async for msg in sse_manager.run_ppt_generation(task_id):
            # 处理消息
            pass
    
    asyncio.create_task(generate_ppt(task_id))
    
    # 3. 前端通过SSE连接获取进度
    # GET /api/courseware/sse/{task_id}
    ```
    """
    
    def __init__(self):
        self._tasks: Dict[str, TaskInfo] = {}
        self._lock = asyncio.Lock()
    
    # ==================== 任务管理 ====================
    
    async def create_task(self, task_type: str, params: Dict) -> str:
        """
        创建新任务
        
        Args:
            task_type: 任务类型 (ppt/lesson_plan/animation/game)
            params: 任务参数
        
        Returns:
            task_id: 任务ID
        """
        async with self._lock:
            task_id = str(uuid.uuid4())[:8]
            self._tasks[task_id] = TaskInfo(task_id, task_type, params)
            return task_id
    
    def create_task_sync(self, task_type: str, params: Dict) -> str:
        """同步版本的任务创建"""
        task_id = str(uuid.uuid4())[:8]
        self._tasks[task_id] = TaskInfo(task_id, task_type, params)
        return task_id
    
    async def get_task(self, task_id: str) -> Optional[TaskInfo]:
        """获取任务信息"""
        async with self._lock:
            return self._tasks.get(task_id)
    
    def get_task_sync(self, task_id: str) -> Optional[TaskInfo]:
        """同步版本的任务获取"""
        return self._tasks.get(task_id)
    
    async def update_task(self, task_id: str, **kwargs):
        """更新任务状态"""
        async with self._lock:
            if task_id in self._tasks:
                task = self._tasks[task_id]
                for key, value in kwargs.items():
                    if hasattr(task, key):
                        setattr(task, key, value)
                task.updated_at = datetime.now()
    
    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        async with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].cancel()
                return True
            return False
    
    async def list_tasks(self, status: Optional[str] = None) -> List[Dict]:
        """列出所有任务"""
        async with self._lock:
            tasks = list(self._tasks.values())
            if status:
                tasks = [t for t in tasks if t.status == status]
            return [t.to_dict() for t in tasks]
    
    async def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        async with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                return True
            return False
    
    # ==================== SSE流 ====================
    
    async def subscribe(self, task_id: str) -> StreamingResponse:
        """
        创建SSE流订阅
        
        Args:
            task_id: 任务ID
        
        Returns:
            StreamingResponse: SSE响应
        """
        async def event_generator():
            queue = asyncio.Queue()
            
            async with self._lock:
                if task_id in self._tasks:
                    self._tasks[task_id]._subscribers.append(queue)
            
            try:
                while True:
                    try:
                        # 等待消息，5秒超时
                        message = await asyncio.wait_for(queue.get(), timeout=5.0)
                        
                        if message == "[CLOSE]":
                            break
                        
                        yield message
                        
                    except asyncio.TimeoutError:
                        # 发送心跳保持连接
                        yield SSEMessage.heartbeat().encode('utf-8')
                        
                        # 检查任务是否还存在
                        async with self._lock:
                            if task_id not in self._tasks:
                                break
                            task = self._tasks[task_id]
                            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                                break
                    except asyncio.CancelledError:
                        break
                        
            finally:
                # 清理订阅
                async with self._lock:
                    if task_id in self._tasks:
                        if queue in self._tasks[task_id]._subscribers:
                            self._tasks[task_id]._subscribers.remove(queue)
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    
    async def broadcast(self, task_id: str, message: str):
        """广播消息到所有订阅者"""
        async with self._lock:
            if task_id in self._tasks:
                task = self._tasks[task_id]
                for queue in task._subscribers:
                    await queue.put(message)
    
    # ==================== 进度更新便捷方法 ====================
    
    async def update_progress(
        self,
        task_id: str,
        stage: str,
        progress: float,
        message: str,
        preview_data: Optional[Dict] = None,
        **kwargs
    ):
        """更新进度并广播"""
        async with self._lock:
            if task_id in self._tasks:
                task = self._tasks[task_id]
                task.stage = stage
                task.progress = progress
                task.message = message
                task.status = TaskStatus.RUNNING
                task.updated_at = datetime.now()
                
                if preview_data:
                    task.preview_data.update(preview_data)
                
                # 计算阶段进度
                stage_progress = self._calculate_stage_progress(stage, progress)
                
                # 构建消息
                msg = SSEMessage.progress(
                    stage=stage,
                    progress=progress,
                    message=message,
                    preview_data=preview_data,
                    stage_progress=stage_progress,
                    **kwargs
                )
                
                # 广播到所有订阅者
                for queue in task._subscribers:
                    await queue.put(msg.encode('utf-8'))
    
    def _calculate_stage_progress(self, stage: str, overall_progress: float) -> float:
        """根据总体进度计算当前阶段进度"""
        stage_weights = {
            GenerationStage.INIT: 5,
            GenerationStage.REQUIREMENTS_PARSING: 10,
GenerationStage.OUTLINE_GENERATION: 15,
            GenerationStage.CONTENT_GENERATION: 40,
            GenerationStage.STYLE_RENDERING: 15,
            GenerationStage.FILE_GENERATION: 10,
            GenerationStage.VALIDATION: 5,
        }
        
        # 计算已完成部分的权重
        stage_order = list(stage_weights.keys())
        if stage not in stage_order:
            return 0
        
        current_idx = stage_order.index(stage)
        completed_weight = sum(stage_weights[stage_order[i]] for i in range(current_idx))
        
        # 计算当前阶段内的进度
        current_weight = stage_weights.get(stage, 10)
        stage_progress = (overall_progress - completed_weight) / current_weight * 100 if current_weight > 0 else 0
        
        return max(0, min(100, stage_progress))
    
    async def stage_start(self, task_id: str, stage: str, message: str = ""):
        """发送阶段开始消息"""
        msg = SSEMessage.stage_start(stage, message)
        async with self._lock:
            if task_id in self._tasks:
                task = self._tasks[task_id]
                task.stage = stage
                task.message = message or GenerationStage.STAGE_DESCRIPTIONS.get(stage, "")
                for queue in task._subscribers:
                    await queue.put(msg.encode('utf-8'))
    
    async def stage_complete(self, task_id: str, stage: str, result: Any = None):
        """发送阶段完成消息"""
        msg = SSEMessage.stage_complete(stage, result)
        async with self._lock:
            if task_id in self._tasks:
                task = self._tasks[task_id]
                task.stage = stage
                if result:
                    task.preview_data.update(result or {})
                for queue in task._subscribers:
                    await queue.put(msg.encode('utf-8'))
    
    async def send_preview(self, task_id: str, page_index: int, page_data: Dict):
        """发送预览更新"""
        msg = SSEMessage.preview_update(page_index, page_data)
        async with self._lock:
            if task_id in self._tasks:
                task = self._tasks[task_id]
                task.preview_data[f"page_{page_index}"] = page_data
                for queue in task._subscribers:
                    await queue.put(msg.encode('utf-8'))
    
    async def send_error(self, task_id: str, error_message: str, error_details: str = ""):
        """发送错误消息"""
        msg = SSEMessage.error(error_message, error_details)
        async with self._lock:
            if task_id in self._tasks:
                task = self._tasks[task_id]
                task.status = TaskStatus.FAILED
                task.error = error_message
                task.updated_at = datetime.now()
                for queue in task._subscribers:
                    await queue.put(msg.encode('utf-8'))
    
    async def complete_task(self, task_id: str, result: Dict):
        """完成任务"""
        msg = SSEMessage.completed(result)
        async with self._lock:
            if task_id in self._tasks:
                task = self._tasks[task_id]
                task.status = TaskStatus.COMPLETED
                task.progress = 100
                task.stage = GenerationStage.COMPLETED
                task.result = result
                task.message = "生成完成"
                task.completed_at = datetime.now()
                task.updated_at = datetime.now()
                
                # 发送完成消息
                for queue in task._subscribers:
                    await queue.put(msg.encode('utf-8'))
                    await queue.put("[CLOSE]")  # 通知关闭
    
    async def close_subscribers(self, task_id: str):
        """关闭所有订阅者的连接"""
        async with self._lock:
            if task_id in self._tasks:
                task = self._tasks[task_id]
                for queue in task._subscribers:
                    await queue.put("[CLOSE]")


# ==================== 全局实例 ====================
# 创建全局SSE管理器实例
sse_manager = SSEProgressManager()


# ==================== API路由 ====================

@router.get("/courseware/sse/{task_id}")
async def sse_stream(task_id: str):
    """
    SSE进度流接口
    
    前端连接此接口获取生成进度
    """
    task = await sse_manager.get_task(task_id)
    if not task:
        return StreamingResponse(
            iter([f"data: {json.dumps({'error': '任务不存在'}, ensure_ascii=False)}\n\n"]),
            media_type="text/event-stream"
        )
    
    return await sse_manager.subscribe(task_id)


@router.get("/courseware/task/{task_id}")
async def get_task_status(task_id: str):
    """获取任务状态"""
    task = await sse_manager.get_task(task_id)
    if not task:
        return {"success": False, "error": "任务不存在"}
    return {"success": True, "task": task.to_dict()}


@router.get("/courseware/tasks")
async def list_tasks(status: Optional[str] = Query(None)):
    """列出所有任务"""
    tasks = await sse_manager.list_tasks(status)
    return {"success": True, "tasks": tasks}


@router.post("/courseware/task/{task_id}/cancel")
async def cancel_task(task_id: str):
    """取消任务"""
    success = await sse_manager.cancel_task(task_id)
    return {"success": success}


@router.delete("/courseware/task/{task_id}")
async def delete_task(task_id: str):
    """删除任务"""
    await sse_manager.close_subscribers(task_id)
    success = await sse_manager.delete_task(task_id)
    return {"success": success}


# ==================== 便捷装饰器 ====================

def track_progress(task_id_var: str = "task_id"):
    """
    进度跟踪装饰器
    
    使用示例:
    ```python
    @track_progress("task_id")
    async def generate_ppt(task_id, params):
        await sse_manager.update_progress(task_id, GenerationStage.INIT, 0, "开始生成...")
        # ... 生成逻辑
        await sse_manager.complete_task(task_id, {"file_path": "/path/to/file.pptx"})
    ```
    """
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            # 从kwargs获取task_id
            task_id = kwargs.get(task_id_var)
            if not task_id:
                raise ValueError(f"Missing required parameter: {task_id_var}")
            
            try:
                return await func(*args, **kwargs)
            except asyncio.CancelledError:
                await sse_manager.send_error(task_id, "任务被取消")
                raise
            except Exception as e:
                await sse_manager.send_error(task_id, str(e), traceback.format_exc())
                raise
        
        return wrapper
    return decorator


# ==================== 导出 ====================
__all__ = [
    "sse_manager",
    "SSEMessage", 
    "TaskInfo",
    "TaskStatus",
    "GenerationStage",
    "SSEProgressManager",
    "router",
    "track_progress"
]
