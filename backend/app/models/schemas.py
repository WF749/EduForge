"""数据模型"""
from typing import List, Optional, Dict
from pydantic import BaseModel

# 聊天消息
class ChatMessage(BaseModel):
    """聊天消息"""
    role: str
    content: str

# 聊天响应
class ChatResponse(BaseModel):
    """聊天响应"""
    success: bool
    message: str
    conversation_id: Optional[str] = None

# 对话历史
class ConversationHistory(BaseModel):
    """对话历史"""
    success: bool
    history: List[Dict]
    conversation_id: str

# 上传文件响应
class UploadResponse(BaseModel):
    """上传文件响应"""
    success: bool
    message: str
    filename: Optional[str] = None
    size: Optional[int] = None

# 知识库查询响应
class KnowledgeQueryResponse(BaseModel):
    """知识库查询响应"""
    success: bool
    results: List[Dict]

# 课件生成响应
class CoursewareResponse(BaseModel):
    """课件生成响应"""
    success: bool
    message: str
    result: Optional[Dict] = None