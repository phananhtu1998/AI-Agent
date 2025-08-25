import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from agent import get_a2a_app, chat_page
from router import conversation_router, health_router, chat_router
from initialize import initialize_all_services, cleanup_all_services
from middleware.cors.cors import configure_cors

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events cho FastAPI app"""
    # Startup
    await initialize_all_services()
    yield
    # Shutdown
    await cleanup_all_services()

# Tạo FastAPI app với lifespan
app = FastAPI(
    title="AI Agent API",
    description="AI Agent với conversation logging và skill routing",
    version="1.0.0",
    lifespan=lifespan
)

# Cấu hình CORS sử dụng middleware có sẵn
configure_cors(app)

# Mount A2A server
a2a_app = get_a2a_app()
app.mount("/", a2a_app)

# Thêm custom HTML route
app.get("/chat", response_class=HTMLResponse)(chat_page)

# Thêm các API routers
app.include_router(conversation_router)
app.include_router(health_router)
app.include_router(chat_router)

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=9999)
