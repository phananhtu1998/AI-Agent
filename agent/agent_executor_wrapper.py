"""
Agent Executor Wrapper - Tự động log conversation khi agent sinh ra kết quả
"""

import time
import logging
import inspect
from typing import Dict, Any, Optional, List
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
            result: Dict[str, Any]

            # Detect underlying executor signature. If it expects (context, event_queue), adapt.
            sig = None
            try:
                sig = inspect.signature(self.agent_executor.execute)
            except Exception:
                sig = None

            # Note: for bound methods, 'self' is not included -> expect 2 params (context, event_queue)
            # For unbound methods, it may be 3 (self, context, event_queue)
            if sig and len(sig.parameters) >= 2:
                # Minimal shims to run A2A-style executors and capture output
                class _DummyEventQueue:
                    def __init__(self):
                        self.events: List[Any] = []
                    async def enqueue_event(self, evt):
                        self.events.append(evt)
                class _DummyContext:
                    def __init__(self, text: str, context_id: str):
                        self._text = text
                        self.context_id = context_id
                        self.task_id = None
                    def get_user_input(self):
                        return self._text
                q = _DummyEventQueue()
                ctx = _DummyContext(user_message, session_id)
                await self.agent_executor.execute(ctx, q)  # type: ignore[arg-type]
                # Extract all agent texts from queued events if available
                collected_texts: List[str] = []
                try:
                    logger.debug(f"Agent event queue length: {len(q.events)}")
                    for evt in q.events:
                        logger.debug(f"Event type: {type(evt)}; has parts: {hasattr(evt, 'parts')}")
                        parts = getattr(evt, 'parts', None)
                        if not parts or not isinstance(parts, list):
                            # Try direct text-like attributes
                            for attr in ("text", "message", "content"):
                                val = getattr(evt, attr, None)
                                if val:
                                    collected_texts.append(str(val))
                                    break
                            # Try dict-like event
                            if hasattr(evt, 'get'):
                                for key in ("text", "message", "content"):
                                    try:
                                        val = evt.get(key)
                                        if val:
                                            collected_texts.append(str(val))
                                            break
                                    except Exception:
                                        pass
                            # As last resort, use string repr if looks short
                            try:
                                s = str(evt)
                                if s and len(s) < 500 and 'TaskStatusUpdateEvent' not in s:
                                    collected_texts.append(s)
                            except Exception:
                                pass
                            continue
                        for part in parts:
                            text_val = None
                            # Direct attribute
                            text_val = getattr(part, 'text', None)
                            # Pydantic/BaseModel export
                            if text_val is None:
                                try:
                                    if hasattr(part, 'model_dump'):
                                        data = part.model_dump()
                                        text_val = data.get('text') or data.get('content')
                                    elif hasattr(part, 'dict'):
                                        data = part.dict()  # type: ignore[attr-defined]
                                        text_val = data.get('text') or data.get('content')
                                except Exception:
                                    pass
                            # Dict
                            if text_val is None and isinstance(part, dict):
                                text_val = part.get('text') or part.get('content') or part.get('message')
                            # Fallback: string cast if short
                            if text_val is None:
                                try:
                                    s = str(part)
                                    if s and len(s) < 500 and 'TaskStatusUpdateEvent' not in s:
                                        text_val = s
                                except Exception:
                                    pass
                            if text_val:
                                collected_texts.append(str(text_val))
                    agent_text = "\n".join(collected_texts).strip()
                except Exception as ex:
                    logger.warning(f"Could not extract agent text from events: {ex}")
                    agent_text = ""
                if not agent_text:
                    logger.warning("No agent text extracted from events; returning fallback message.")
                # Try to extract skill/intent from underlying executor if available
                skill = None
                try:
                    underlying = getattr(self, 'agent_executor', None)
                    # IntentRouterAgentExecutor exposes last_intent
                    skill = getattr(underlying, 'last_intent', None)
                except Exception:
                    pass
                result = {
                    "response": agent_text or "Không có nội dung phản hồi.",
                    "skill_used": skill or "unknown",
                }
            else:
                # Legacy/simple signature (user_message, **kwargs)
                result = await self.agent_executor.execute(user_message, **kwargs)  # type: ignore[misc]
            
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
