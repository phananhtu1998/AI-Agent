"""
Chat Models - Pydantic models cho chat API
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class ChatRequest(BaseModel):
    """Model cho request chat"""
    message: str = Field(..., description="Tin nhắn từ user", min_length=1)
    session_id: Optional[str] = Field(None, description="ID của session (tự động tạo nếu không có)")
    user_id: Optional[str] = Field(None, description="ID của user")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Metadata bổ sung")

class ChatResponse(BaseModel):
    """Model cho response chat"""
    success: bool = Field(..., description="Trạng thái xử lý")
    message: str = Field(..., description="Thông báo kết quả")
    response: str = Field(..., description="Phản hồi từ agent")
    session_id: str = Field(..., description="ID của session")
    skill_used: Optional[str] = Field(None, description="Skill được sử dụng")
    processing_time: float = Field(..., description="Thời gian xử lý (giây)")
    conversation_id: Optional[str] = Field(None, description="ID của conversation")

class ChatSessionInfo(BaseModel):
    """Model cho thông tin session chat"""
    session_id: str = Field(..., description="ID của session")
    summary: Optional[Dict[str, Any]] = Field(None, description="Summary của session")
    recent_conversations: list = Field(default_factory=list, description="Danh sách conversation gần đây")
    total_conversations: int = Field(0, description="Tổng số conversation")
