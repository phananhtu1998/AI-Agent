"""
Conversation Service - Business logic cho conversation logging và management
"""

import logging
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from utils import db_execute, db_fetch_all, db_fetch_one, redis_set, redis_get, redis_delete

logger = logging.getLogger(__name__)

class ConversationService:
    """Service để quản lý conversation logging và retrieval"""
    
    @staticmethod
    async def log_conversation(
        session_id: str,
        user_message: str,
        agent_response: str,
        skill_used: str = None,
        processing_time: float = None,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """
        Lưu thông tin conversation vào database
        
        Args:
            session_id: ID của session
            user_message: Tin nhắn của user
            agent_response: Phản hồi của agent
            skill_used: Skill được sử dụng
            processing_time: Thời gian xử lý (giây)
            metadata: Thông tin bổ sung
        """
        try:
            # Tạo conversation ID
            conversation_id = str(uuid.uuid4())
            timestamp = datetime.now()
            
            # Lưu vào PostgreSQL
            query = """
                INSERT INTO conversations (
                    conversation_id, session_id, user_message, agent_response, 
                    skill_used, processing_time, metadata, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """
            
            metadata_json = json.dumps(metadata) if metadata else None
            
            await db_execute(query, (
                conversation_id,
                session_id,
                user_message,
                agent_response,
                skill_used,
                processing_time,
                metadata_json,
                timestamp
            ))
            
            # Cache conversation gần đây trong Redis
            await ConversationService._cache_conversation(
                session_id, conversation_id, user_message, 
                agent_response, skill_used, processing_time, timestamp
            )
            
            # Cập nhật session summary
            await ConversationService._update_session_summary(session_id, conversation_id)
            
            logger.info(f"Conversation logged successfully: {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error logging conversation: {str(e)}")
            return False
    
    @staticmethod
    async def _cache_conversation(
        session_id: str, 
        conversation_id: str, 
        user_message: str, 
        agent_response: str, 
        skill_used: str, 
        processing_time: float, 
        timestamp: datetime
    ):
        """Cache conversation trong Redis"""
        try:
            cache_key = f"conversation:{session_id}:{conversation_id}"
            cache_data = {
                "conversation_id": conversation_id,
                "user_message": user_message,
                "agent_response": agent_response,
                "skill_used": skill_used,
                "processing_time": processing_time,
                "timestamp": timestamp.isoformat()
            }
            
            await redis_set(cache_key, json.dumps(cache_data), expire=3600)  # Cache 1 giờ
            
        except Exception as e:
            logger.error(f"Error caching conversation: {str(e)}")
    
    @staticmethod
    async def _update_session_summary(session_id: str, conversation_id: str):
        """Cập nhật summary của session trong Redis"""
        try:
            summary_key = f"session_summary:{session_id}"
            
            # Lấy summary hiện tại
            current_summary = await redis_get(summary_key)
            if current_summary:
                summary = json.loads(current_summary)
            else:
                summary = {
                    "session_id": session_id,
                    "total_conversations": 0,
                    "last_conversation_id": None,
                    "created_at": datetime.now().isoformat()
                }
            
            # Cập nhật summary
            summary["total_conversations"] += 1
            summary["last_conversation_id"] = conversation_id
            summary["updated_at"] = datetime.now().isoformat()
            
            # Lưu lại vào Redis
            await redis_set(summary_key, json.dumps(summary), expire=86400)  # Cache 24 giờ
            
        except Exception as e:
            logger.error(f"Error updating session summary: {str(e)}")
    
    @staticmethod
    async def get_conversation_history(
        session_id: str, 
        limit: int = 10,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Lấy lịch sử conversation của một session"""
        try:
            query = """
                SELECT conversation_id, user_message, agent_response, 
                       skill_used, processing_time, metadata, created_at
                FROM conversations 
                WHERE session_id = $1 
                ORDER BY created_at DESC 
                LIMIT $2 OFFSET $3
            """
            
            conversations = await db_fetch_all(query, (session_id, limit, offset))
            
            # Parse metadata JSON
            for conv in conversations:
                if conv.get('metadata'):
                    try:
                        conv['metadata'] = json.loads(conv['metadata'])
                    except:
                        conv['metadata'] = None
            
            return conversations
            
        except Exception as e:
            logger.error(f"Error getting conversation history: {str(e)}")
            return []
    
    @staticmethod
    async def get_session_summary(session_id: str) -> Optional[Dict[str, Any]]:
        """Lấy summary của session"""
        try:
            # Thử lấy từ Redis cache trước
            cache_key = f"session_summary:{session_id}"
            cached_summary = await redis_get(cache_key)
            
            if cached_summary:
                return json.loads(cached_summary)
            
            # Nếu không có trong cache, tính toán từ database
            query = """
                SELECT 
                    COUNT(*) as total_conversations,
                    MAX(created_at) as last_conversation_at,
                    MIN(created_at) as first_conversation_at,
                    AVG(processing_time) as avg_processing_time
                FROM conversations 
                WHERE session_id = $1
            """
            
            result = await db_fetch_one(query, (session_id,))
            
            if result:
                summary = {
                    "session_id": session_id,
                    "total_conversations": result['total_conversations'],
                    "last_conversation_at": result['last_conversation_at'].isoformat() if result['last_conversation_at'] else None,
                    "first_conversation_at": result['first_conversation_at'].isoformat() if result['first_conversation_at'] else None,
                    "avg_processing_time": float(result['avg_processing_time']) if result['avg_processing_time'] else None,
                    "created_at": datetime.now().isoformat()
                }
                
                # Cache summary
                await redis_set(cache_key, json.dumps(summary), expire=86400)
                return summary
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting session summary: {str(e)}")
            return None
    
    @staticmethod
    async def get_conversation_by_id(conversation_id: str) -> Optional[Dict[str, Any]]:
        """Lấy thông tin conversation theo ID"""
        try:
            # Thử lấy từ Redis cache trước
            cache_key = f"conversation_detail:{conversation_id}"
            cached_data = await redis_get(cache_key)
            
            if cached_data:
                return json.loads(cached_data)
            
            # Lấy từ database
            query = """
                SELECT conversation_id, session_id, user_message, agent_response,
                       skill_used, processing_time, metadata, created_at
                FROM conversations 
                WHERE conversation_id = $1
            """
            
            conversation = await db_fetch_one(query, (conversation_id,))
            
            if conversation:
                # Parse metadata
                if conversation.get('metadata'):
                    try:
                        conversation['metadata'] = json.loads(conversation['metadata'])
                    except:
                        conversation['metadata'] = None
                
                # Cache kết quả
                await redis_set(cache_key, json.dumps(conversation), expire=3600)
                return conversation
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting conversation by ID: {str(e)}")
            return None
    
    @staticmethod
    async def delete_session(session_id: str) -> bool:
        """Xóa toàn bộ session và conversations"""
        try:
            # Xóa conversations từ database
            await db_execute(
                "DELETE FROM conversations WHERE session_id = $1",
                (session_id,)
            )
            
            # Xóa cache Redis
            await redis_delete(f"session_summary:{session_id}")
            
            logger.info(f"Session {session_id} deleted successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {str(e)}")
            return False
    
    @staticmethod
    async def get_conversation_stats() -> Dict[str, Any]:
        """Lấy thống kê tổng quan về conversations"""
        try:
            # Lấy thống kê tổng quan
            stats_query = """
                SELECT 
                    COUNT(DISTINCT session_id) as total_sessions,
                    COUNT(*) as total_conversations,
                    AVG(processing_time) as avg_processing_time,
                    MAX(created_at) as last_conversation_at
                FROM conversations
            """
            
            stats = await db_fetch_one(stats_query)
            
            # Lấy skill được sử dụng nhiều nhất
            skill_query = """
                SELECT 
                    skill_used,
                    COUNT(*) as usage_count
                FROM conversations 
                WHERE skill_used IS NOT NULL 
                GROUP BY skill_used 
                ORDER BY usage_count DESC 
                LIMIT 1
            """
            
            top_skill = await db_fetch_one(skill_query)
            
            # Lấy thống kê theo ngày (7 ngày gần nhất)
            daily_stats_query = """
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as conversations,
                    AVG(processing_time) as avg_time
                FROM conversations 
                WHERE created_at >= NOW() - INTERVAL '7 days'
                GROUP BY DATE(created_at)
                ORDER BY date DESC
            """
            
            daily_stats = await db_fetch_all(daily_stats_query)
            
            return {
                "total_sessions": stats['total_sessions'] if stats else 0,
                "total_conversations": stats['total_conversations'] if stats else 0,
                "avg_processing_time": float(stats['avg_processing_time']) if stats and stats['avg_processing_time'] else 0,
                "last_conversation_at": stats['last_conversation_at'].isoformat() if stats and stats['last_conversation_at'] else None,
                "most_used_skill": top_skill['skill_used'] if top_skill else None,
                "skill_usage_count": top_skill['usage_count'] if top_skill else 0,
                "daily_stats": daily_stats,
                "last_7_days": len(daily_stats)
            }
            
        except Exception as e:
            logger.error(f"Error getting conversation stats: {str(e)}")
            return {}

# Convenience functions
async def log_agent_response(
    session_id: str,
    user_message: str,
    agent_response: str,
    skill_used: str = None,
    processing_time: float = None,
    metadata: Dict[str, Any] = None
) -> bool:
    """Lưu phản hồi của agent"""
    return await ConversationService.log_conversation(
        session_id, user_message, agent_response, skill_used, processing_time, metadata
    )

async def get_conversation_history(session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Lấy lịch sử conversation"""
    return await ConversationService.get_conversation_history(session_id, limit)

async def get_session_summary(session_id: str) -> Optional[Dict[str, Any]]:
    """Lấy summary của session"""
    return await ConversationService.get_session_summary(session_id)

async def delete_session(session_id: str) -> bool:
    """Xóa session"""
    return await ConversationService.delete_session(session_id)

async def get_conversation_stats() -> Dict[str, Any]:
    """Lấy thống kê conversation"""
    return await ConversationService.get_conversation_stats()
