"""FastAPI app: static frontend + REST data API + WebSocket runner/terminals."""
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import chat, config, data_api, runner, security, terminal

app = FastAPI(title="Tennis Mission Control", docs_url=None, redoc_url=None)

app.include_router(data_api.router)
app.include_router(runner.router)
app.include_router(terminal.router)
app.include_router(chat.router)

_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://unpkg.com; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
    "img-src 'self' data: blob:; "
    "media-src 'self' blob:; "
    "font-src 'self' data:; "
    "connect-src 'self' ws: wss:; "
    "frame-src 'self'; "
    "frame-ancestors 'self'; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "form-action 'self'"
)


@app.middleware("http")
async def security_headers(request, call_next):
    if (request.url.path.startswith("/api/")
            and security.browser_request_is_cross_origin(request.headers)):
        response = JSONResponse(
            {"error": "forbidden", "detail": "cross-origin dashboard request rejected"},
            status_code=403,
        )
    else:
        response = await call_next(request)
    response.headers["Content-Security-Policy"] = _CONTENT_SECURITY_POLICY
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    return response


@app.get("/")
def index():
    return FileResponse(config.STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")
