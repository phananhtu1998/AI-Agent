"""
Health Routes - Các routes để kiểm tra trạng thái hệ thống
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/health", tags=["health"])

@router.get("/")
async def health_check():
    """Health check endpoint"""
    return JSONResponse({
        "status": "healthy",
        "message": "AI Agent is running with conversation logging",
        "version": "1.0.0"
    })

@router.get("/ping")
async def ping():
    """Simple ping endpoint"""
    return JSONResponse({
        "pong": True,
        "timestamp": "2024-01-01T00:00:00Z"
    })

@router.get("/status")
async def system_status():
    """Detailed system status"""
    return JSONResponse({
        "status": "operational",
        "services": {
            "agent": "running",
            "database": "connected",
            "redis": "connected",
            "conversation_logging": "enabled"
        },
        "uptime": "N/A",  # Có thể implement để lấy uptime thực
        "version": "1.0.0"
    })
