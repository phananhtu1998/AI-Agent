"""
Conversation Models - Pydantic models cho conversation API
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class ConversationLogRequest(BaseModel):
    """Model cho request log conversation thủ công"""
    session_id: str = Field(..., description="ID của session")
    user_message: str = Field(..., description="Tin nhắn của user")
    agent_response: str = Field(..., description="Phản hồi của agent")
    skill_used: Optional[str] = Field(None, description="Skill được sử dụng")
    processing_time: Optional[float] = Field(None, description="Thời gian xử lý (giây)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Metadata bổ sung")

class ConversationLogResponse(BaseModel):
    """Model cho response log conversation"""
    success: bool = Field(..., description="Trạng thái logging")
    session_id: str = Field(..., description="ID của session")
    message: str = Field(..., description="Thông báo kết quả")

class ConversationHistoryResponse(BaseModel):
    """Model cho response conversation history"""
    session_id: str = Field(..., description="ID của session")
    conversations: list = Field(default_factory=list, description="Danh sách conversations")
    count: int = Field(0, description="Số lượng conversation")

class ConversationSummaryResponse(BaseModel):
    """Model cho response conversation summary"""
    session_id: str = Field(..., description="ID của session")
    summary: Optional[Dict[str, Any]] = Field(None, description="Summary của session")

class ConversationStatsResponse(BaseModel):
    """Model cho response conversation stats"""
    total_sessions: int = Field(0, description="Tổng số sessions")
    total_conversations: int = Field(0, description="Tổng số conversations")
    avg_processing_time: float = Field(0.0, description="Thời gian xử lý trung bình")
    last_conversation_at: Optional[str] = Field(None, description="Thời gian conversation cuối cùng")
    most_used_skill: Optional[str] = Field(None, description="Skill được sử dụng nhiều nhất")
    skill_usage_count: int = Field(0, description="Số lần sử dụng skill phổ biến nhất")
    daily_stats: list = Field(default_factory=list, description="Thống kê theo ngày")
    last_7_days: int = Field(0, description="Số ngày có dữ liệu")

class TestLogResponse(BaseModel):
    """Model cho response test log"""
    success: bool = Field(..., description="Trạng thái test")
    session_id: str = Field(..., description="ID của session test")
    message: str = Field(..., description="Thông báo kết quả test")
