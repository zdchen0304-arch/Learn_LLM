"""
MAARS Backend - FastAPI + Socket.io entry point.
Python implementation of the MAARS backend.
"""

import asyncio
import os
from pathlib import Path

import socketio
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from api import register_routes
from api import state as api_state
from shared.logging_config import configure_backend_file_logging

def _cors_origins() -> list[str]:
    """Read explicit browser origins instead of allowing credentialed requests from everywhere."""
    raw = os.getenv("MAARS_CORS_ORIGINS", "http://localhost:3001,http://127.0.0.1:3001")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


CORS_ORIGINS = _cors_origins()

# Socket.io keeps a compatibility channel for existing clients. SSE is the primary stream.
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=CORS_ORIGINS)
app = FastAPI(title="MAARS Backend")


@app.on_event("startup")
async def _print_browser_url():
    """Print the URL to open in browser (0.0.0.0 is not openable in browser)."""
    configure_backend_file_logging()
    import sys
    print("INFO:     Open in browser: http://localhost:3001", file=sys.stderr, flush=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz", include_in_schema=False)
async def healthcheck() -> dict[str, str]:
    """Container and orchestrator readiness probe without exposing session data."""
    return {"status": "ok"}

# Register API routes (Idea, Plan, Task, Paper, ...)
register_routes(app, sio)


# Disable cache for static files (dev: always fetch latest)
NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}


class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path == "/" or path.endswith((".html", ".css", ".js")):
            for k, v in NO_CACHE_HEADERS.items():
                response.headers[k] = v
        return response


app.add_middleware(NoCacheMiddleware)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Centralized exception handler for unhandled errors."""
    logger.exception("Unhandled exception: {}", exc)
    return JSONResponse(
        status_code=500,
        content={"error": str(exc) or "Internal server error"},
    )


# Frontend static files
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="static")


# Socket.io events
@sio.event
async def connect(sid, environ, auth):
    try:
        session_id = api_state.resolve_socket_session_id(auth)
    except ValueError as e:
        logger.warning("Socket auth rejected sid=%s error=%s", sid, e)
        raise ConnectionRefusedError(str(e))
    api_state.bind_socket_to_session(sid, session_id)
    await sio.enter_room(sid, session_id)
    await api_state.get_or_create_session_state(session_id)
    logger.info("Client connected: %s session=%s", sid, session_id)


@sio.event
async def disconnect(sid):
    await api_state.unbind_socket(sid)
    logger.info("Client disconnected: %s", sid)


# ASGI app for uvicorn (Socket.io + FastAPI)
asgi_app = socketio.ASGIApp(sio, app)
