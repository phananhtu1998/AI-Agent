"""
Agent Executor Wrapper - Tự động log conversation khi agent sinh ra kết quả
"""

import time
import logging
from typing import Dict, Any, Optional
from service import log_agent_response

logger = logging.getLogger(__name__)

class AgentExecutorWrapper:
    """Wrapper cho agent executor để tự động log conversation"""
    
    def __init__(self, agent_executor):
        self.agent_executor = agent_executor
    
    async def execute(self, session_id: str, user_message: str, **kwargs) -> Dict[str, Any]:
        """
        Thực thi agent và tự động log conversation
        
        Args:
            session_id: ID của session
            user_message: Tin nhắn của user
            **kwargs: Các tham số khác cho agent executor
        """
        start_time = time.time()
        
        try:
            # Thực thi agent
            result = await self.agent_executor.execute(user_message, **kwargs)
            
            # Tính thời gian xử lý
            processing_time = time.time() - start_time
            
            # Lấy thông tin skill được sử dụng
            skill_used = self._extract_skill_used(result)
            
            # Lấy response của agent
            agent_response = self._extract_agent_response(result)
            
            # Metadata bổ sung
            metadata = {
                "executor_type": type(self.agent_executor).__name__,
                "processing_time": processing_time,
                "result_keys": list(result.keys()) if isinstance(result, dict) else None,
                "kwargs": kwargs
            }
            
            # Log conversation
            await log_agent_response(
                session_id=session_id,
                user_message=user_message,
                agent_response=agent_response,
                skill_used=skill_used,
                processing_time=processing_time,
                metadata=metadata
            )
            
            logger.info(f"Agent executed successfully for session {session_id}, skill: {skill_used}")
            
            return result
            
        except Exception as e:
            # Log lỗi
            processing_time = time.time() - start_time
            error_response = f"Error: {str(e)}"
            
            await log_agent_response(
                session_id=session_id,
                user_message=user_message,
                agent_response=error_response,
                skill_used="error",
                processing_time=processing_time,
                metadata={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "executor_type": type(self.agent_executor).__name__
                }
            )
            
            logger.error(f"Agent execution failed for session {session_id}: {str(e)}")
            raise
    
    def _extract_skill_used(self, result: Dict[str, Any]) -> Optional[str]:
        """Trích xuất skill được sử dụng từ kết quả"""
        try:
            if isinstance(result, dict):
                # Kiểm tra các key có thể chứa thông tin skill
                skill_keys = ['skill', 'skill_used', 'intent', 'action', 'type']
                for key in skill_keys:
                    if key in result:
                        return str(result[key])
                
                # Kiểm tra trong metadata
                if 'metadata' in result and isinstance(result['metadata'], dict):
                    for key in skill_keys:
                        if key in result['metadata']:
                            return str(result['metadata'][key])
            
            return None
            
        except Exception as e:
            logger.warning(f"Could not extract skill used: {str(e)}")
            return None
    
    def _extract_agent_response(self, result: Dict[str, Any]) -> str:
        """Trích xuất response của agent từ kết quả"""
        try:
            if isinstance(result, dict):
                # Thử các key có thể chứa response
                response_keys = ['response', 'answer', 'content', 'text', 'message', 'output']
                for key in response_keys:
                    if key in result and result[key]:
                        return str(result[key])
                
                # Nếu không tìm thấy, chuyển toàn bộ result thành string
                return str(result)
            
            return str(result)
            
        except Exception as e:
            logger.warning(f"Could not extract agent response: {str(e)}")
            return str(result)

def wrap_agent_executor(agent_executor) -> AgentExecutorWrapper:
    """Wrap agent executor để tự động log conversation"""
    return AgentExecutorWrapper(agent_executor)
