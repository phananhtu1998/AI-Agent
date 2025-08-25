"""
Agent package - chứa các chức năng chính của AI Agent
"""

from .skills import create_chat_skill, create_weather_skill, get_all_skills
from .cards import create_public_agent_card, create_extended_agent_card
from .routes import chat_page
from .app_factory import get_a2a_app, create_a2a_server, create_request_handler
from .agent_executor_wrapper import AgentExecutorWrapper, wrap_agent_executor

# Import conversation functions từ service package
from service import (
    log_agent_response,
    get_conversation_history,
    get_session_summary,
    delete_session,
    get_conversation_stats
)

# Import database functions từ utils package
from utils import (
    db_execute, db_fetch_all, db_fetch_one,
    redis_set, redis_get, redis_delete, redis_exists
)

__all__ = [
    'create_chat_skill',
    'create_weather_skill', 
    'get_all_skills',
    'create_public_agent_card',
    'create_extended_agent_card',
    'chat_page',
    'get_a2a_app',
    'create_a2a_server',
    'create_request_handler',
    'AgentExecutorWrapper',
    'wrap_agent_executor',
    'log_agent_response',
    'get_conversation_history',
    'get_session_summary',
    'delete_session',
    'get_conversation_stats',
    'db_execute',
    'db_fetch_all', 
    'db_fetch_one',
    'redis_set',
    'redis_get',
    'redis_delete',
    'redis_exists'
]
