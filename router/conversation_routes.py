"""
Conversation Routes - Các routes để test và quản lý conversation logging
"""

import uuid
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from models import (
    ConversationLogRequest, ConversationLogResponse, ConversationHistoryResponse,
    ConversationSummaryResponse, ConversationStatsResponse, TestLogResponse
)
from service import get_conversation_history, get_session_summary, log_agent_response, get_conversation_stats

router = APIRouter(prefix="/conversation", tags=["conversation"])

@router.get("/test-log", response_model=TestLogResponse)
async def test_log():
    """Test endpoint để log conversation"""
    session_id = str(uuid.uuid4())
    
    # Log một conversation test
    success = await log_agent_response(
        session_id=session_id,
        user_message="Xin chào, bạn có thể giúp tôi không?",
        agent_response="Chào bạn! Tôi có thể giúp bạn với các câu hỏi về chat tổng quát hoặc thời tiết.",
        skill_used="chat",
        processing_time=1.5,
        metadata={"test": True, "source": "test-endpoint"}
    )
    
    return TestLogResponse(
        success=success,
        session_id=session_id,
        message="Test conversation logged"
    )

@router.get("/history/{session_id}", response_model=ConversationHistoryResponse)
async def get_conversations(session_id: str, limit: int = 10):
    """Lấy lịch sử conversation của một session"""
    try:
        conversations = await get_conversation_history(session_id, limit=limit)
        return ConversationHistoryResponse(
            session_id=session_id,
            conversations=conversations,
            count=len(conversations)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/summary/{session_id}", response_model=ConversationSummaryResponse)
async def get_session_info(session_id: str):
    """Lấy summary của session"""
    try:
        summary = await get_session_summary(session_id)
        return ConversationSummaryResponse(
            session_id=session_id,
            summary=summary
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/log", response_model=ConversationLogResponse)
async def log_conversation(request: ConversationLogRequest):
    """Log conversation thủ công"""
    try:
        success = await log_agent_response(
            session_id=request.session_id,
            user_message=request.user_message,
            agent_response=request.agent_response,
            skill_used=request.skill_used,
            processing_time=request.processing_time,
            metadata=request.metadata
        )
        
        return ConversationLogResponse(
            success=success,
            session_id=request.session_id,
            message="Conversation logged successfully" if success else "Failed to log conversation"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats", response_model=ConversationStatsResponse)
async def get_conversation_stats_endpoint():
    """Lấy thống kê tổng quan về conversations"""
    try:
        stats = await get_conversation_stats()
        return ConversationStatsResponse(**stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
