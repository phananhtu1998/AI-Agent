import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from agent_executor import RouterAgentExecutor  # type: ignore[import-untyped]

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware


if __name__ == '__main__':
    chat_skill = AgentSkill(
        id='chat',
        name='Chat tổng quát (Gemini)',
        description='Trả lời câu hỏi chung qua Gemini',
        tags=['chat', 'gemini'],
        examples=['Xin chào', 'giải thích về AI'],
    )

    weather_skill = AgentSkill(
        id='weather',
        name='Thời tiết theo tỉnh/thành',
        description='Hỏi thời tiết; yêu cầu nêu rõ tỉnh/thành',
        tags=['weather', 'thời tiết'],
        examples=['Thời tiết Hà Nội', 'Thời tiết ở Đà Nẵng hôm nay'],
    )

    # Public-facing agent card
    public_agent_card = AgentCard(
        name='Router Agent',
        description='Điều phối giữa chat (Gemini) và thời tiết',
        url='http://localhost:9999/',
        version='1.0.0',
        default_input_modes=['text'],
        default_output_modes=['text'],
        capabilities=AgentCapabilities(streaming=True),
        skills=[chat_skill, weather_skill],
        supports_authenticated_extended_card=True,
    )

    # Authenticated extended agent card
    specific_extended_agent_card = public_agent_card.model_copy(
        update={
            'name': 'Router Agent - Extended',
            'description': 'Phiên bản đầy đủ cho người dùng xác thực',
            'version': '1.0.1',
            'skills': [chat_skill, weather_skill],
        }
    )

    request_handler = DefaultRequestHandler(
        agent_executor=RouterAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    server = A2AStarletteApplication(
        agent_card=public_agent_card,
        http_handler=request_handler,
        extended_agent_card=specific_extended_agent_card,
    )

    # Build Starlette app rồi bọc lại bằng FastAPI
    starlette_app = server.build()
    app = FastAPI()
    app.mount("/", starlette_app)  # giữ nguyên tất cả route của A2A

    # Enable CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=['*'],
        allow_methods=['*'],
        allow_headers=['*'],
        allow_credentials=False,
    )

    # Route /chat theo kiểu FastAPI decorator
    @app.get("/chat", response_class=HTMLResponse)
    async def chat_page(request: Request):
        try:
            with open("chat.html", "r", encoding="utf-8") as f:
                html = f.read()
        except Exception:
            html = "<!doctype html><html><body><p>chat.html not found.</p></body></html>"
        return HTMLResponse(html)

    uvicorn.run(app, host="0.0.0.0", port=9999)
