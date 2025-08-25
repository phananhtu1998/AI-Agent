from fastapi import Request
from fastapi.responses import HTMLResponse

async def chat_page(request: Request) -> HTMLResponse:
    """Route handler cho trang chat"""
    try:
        with open("chat.html", "r", encoding="utf-8") as f:
            html = f.read()
    except Exception:
        html = "<!doctype html><html><body><p>chat.html not found.</p></body></html>"
    return HTMLResponse(html)
