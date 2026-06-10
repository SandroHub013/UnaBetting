"""FastAPI app: static frontend + REST data API + WebSocket runner/terminals."""
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import chat, config, data_api, runner, terminal

app = FastAPI(title="Tennis Mission Control", docs_url=None, redoc_url=None)

app.include_router(data_api.router)
app.include_router(runner.router)
app.include_router(terminal.router)
app.include_router(chat.router)


@app.get("/")
def index():
    return FileResponse(config.STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")
