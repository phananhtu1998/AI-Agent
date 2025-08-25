import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from agent import get_a2a_app
from router import conversation_router, health_router, chat_router
from initialize import initialize_all_services, cleanup_all_services
from middleware.cors.cors import configure_cors
from agent_executor import WeatherAgentExecutor

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events cho FastAPI app"""
    # Startup
    await initialize_all_services()
    # Preload Vietnam locations once at startup
    try:
        await WeatherAgentExecutor.preload_locations()
        print("DEBUG: Preloaded Vietnam locations at startup")
    except Exception as e:
        print(f"DEBUG: Failed to preload locations at startup: {e}")
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

# Thêm các API routers TRƯỚC khi mount A2A server
app.include_router(conversation_router)
app.include_router(health_router)
app.include_router(chat_router)

# Mount A2A server ở path khác để không override API routes
a2a_app = get_a2a_app()
app.mount("/a2a", a2a_app)  # Thay đổi từ "/" thành "/a2a"

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=9999)
