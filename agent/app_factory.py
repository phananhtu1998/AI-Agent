from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from agent_executor import IntentRouterAgentExecutor  # type: ignore[import-untyped]

from .cards import create_public_agent_card, create_extended_agent_card
from .routes import chat_page
from .agent_executor_wrapper import wrap_agent_executor

def create_request_handler() -> DefaultRequestHandler:
    """Tạo request handler cho agent với conversation logging"""
    # Tạo agent executor gốc
    original_executor = IntentRouterAgentExecutor()
    
    # Wrap với conversation logging
    wrapped_executor = wrap_agent_executor(original_executor)
    
    return DefaultRequestHandler(
        agent_executor=wrapped_executor,
        task_store=InMemoryTaskStore(),
    )

def create_a2a_server() -> A2AStarletteApplication:
    """Tạo A2A server application"""
    request_handler = create_request_handler()
    public_card = create_public_agent_card()
    extended_card = create_extended_agent_card()
    
    return A2AStarletteApplication(
        agent_card=public_card,
        http_handler=request_handler,
        extended_agent_card=extended_card,
    )

def get_a2a_app():
    """Lấy A2A Starlette app để mount vào FastAPI"""
    a2a_server = create_a2a_server()
    return a2a_server.build()
