"""
Chat Routes - API để tương tác với agent
"""

import uuid
import time
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any
from models import ChatRequest, ChatResponse, ChatSessionInfo
from service import log_agent_response, delete_session
from agent import create_request_handler

router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("/", response_model=ChatResponse)
async def chat_with_agent(request: ChatRequest, http_request: Request):
    """
    API endpoint để chat với agent
    
    Args:
        request: ChatRequest chứa message và metadata
        http_request: FastAPI Request object để lấy thông tin client
    
    Returns:
        ChatResponse với response từ agent
    """
    start_time = time.time()
    
    try:
        # Tạo session_id nếu không có
        session_id = request.session_id or str(uuid.uuid4())
        
        # Lấy thông tin client
        client_info = {
            "ip": http_request.client.host if http_request.client else "unknown",
            "user_agent": http_request.headers.get("user-agent", "unknown"),
            "method": http_request.method,
            "url": str(http_request.url)
        }
        
        # Metadata kết hợp
        metadata = {
            "client_info": client_info,
            "user_id": request.user_id,
            "source": "api",
            "timestamp": time.time()
        }
        
        if request.metadata:
            metadata.update(request.metadata)
        
        # Gọi agent executor để xử lý message
        agent_response = await process_message_with_agent(request.message, session_id)
        
        # Tính thời gian xử lý
        processing_time = time.time() - start_time
        
        # Log conversation
        conversation_id = str(uuid.uuid4())
        success = await log_agent_response(
            session_id=session_id,
            user_message=request.message,
            agent_response=agent_response["response"],
            skill_used=agent_response.get("skill_used"),
            processing_time=processing_time,
            metadata=metadata
        )
        
        # Trả về response
        return ChatResponse(
            success=success,
            message="Chat processed successfully" if success else "Chat processed but logging failed",
            response=agent_response["response"],
            session_id=session_id,
            skill_used=agent_response.get("skill_used"),
            processing_time=processing_time,
            conversation_id=conversation_id
        )
        
    except Exception as e:
        # Log lỗi
        processing_time = time.time() - start_time
        error_response = f"Error: {str(e)}"
        
        try:
            await log_agent_response(
                session_id=session_id if 'session_id' in locals() else str(uuid.uuid4()),
                user_message=request.message,
                agent_response=error_response,
                skill_used="error",
                processing_time=processing_time,
                metadata={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "source": "api"
                }
            )
        except:
            pass  # Ignore logging errors
        
        raise HTTPException(status_code=500, detail=str(e))

async def process_message_with_agent(message: str, session_id: str) -> Dict[str, Any]:
    """
    Xử lý message với agent executor
    
    Args:
        message: Tin nhắn từ user
        session_id: ID của session
    
    Returns:
        Dict chứa response và metadata
    """
    try:
        # Tạo request handler với agent executor đã được wrap
        request_handler = create_request_handler()
        
        # Gọi agent executor để xử lý message
        result = await request_handler.agent_executor.execute(
            session_id=session_id,
            user_message=message
        )
        
        # Trích xuất response và skill
        response = result.get("response", str(result))
        skill_used = result.get("skill_used", "unknown")
        
        return {
            "response": response,
            "skill_used": skill_used
        }
        
    except Exception as e:
        # Fallback response nếu có lỗi
        return {
            "response": f"Xin lỗi, tôi gặp vấn đề khi xử lý tin nhắn của bạn: {str(e)}",
            "skill_used": "error"
        }

@router.get("/session/{session_id}", response_model=ChatSessionInfo)
async def get_chat_session(session_id: str):
    """Lấy thông tin session chat"""
    try:
        from service import get_session_summary, get_conversation_history
        
        # Lấy session summary
        summary = await get_session_summary(session_id)
        
        # Lấy conversation history
        history = await get_conversation_history(session_id, limit=20)
        
        return ChatSessionInfo(
            session_id=session_id,
            summary=summary,
            recent_conversations=history,
            total_conversations=len(history)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/session/{session_id}")
async def delete_chat_session(session_id: str):
    """Xóa session chat"""
    try:
        success = await delete_session(session_id)
        
        if success:
            return JSONResponse({
                "success": True,
                "message": f"Session {session_id} đã được xóa thành công"
            })
        else:
            raise HTTPException(status_code=500, detail="Không thể xóa session")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
