"""API surface for Redis-context / RabbitMQ-dispatched research commands."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from async_runtime import AsyncResearchRuntime, RuntimeUnavailableError
from db import get_research, list_async_tasks

from .. import state as api_state
from ..schemas import AsyncTaskDispatchRequest


router = APIRouter()
_runtime: AsyncResearchRuntime | None = None


def get_async_runtime() -> AsyncResearchRuntime:
    global _runtime
    if _runtime is None:
        _runtime = AsyncResearchRuntime.from_env()
    return _runtime


@router.get("/async-runtime/status")
async def get_async_runtime_status(request: Request):
    """Report backend readiness without exposing Redis/RabbitMQ connection URLs."""
    await api_state.require_session(request)
    try:
        return await get_async_runtime().health()
    except RuntimeUnavailableError as exc:
        return {"ready": False, "error": str(exc)}


@router.post("/research/{research_id}/async-tasks", status_code=202)
async def dispatch_async_task(research_id: str, body: AsyncTaskDispatchRequest, request: Request):
    await api_state.require_session(request)
    research = await get_research(research_id)
    if not research:
        return JSONResponse(status_code=404, content={"error": "Research not found"})
    try:
        result = await get_async_runtime().dispatch(
            research=research,
            stage=body.stage,
            artifact_refs=body.artifact_refs,
            idempotency_key=body.idempotency_key,
            max_attempts=body.max_attempts,
        )
    except RuntimeUnavailableError as exc:
        return JSONResponse(status_code=503, content={"error": str(exc)})
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    if result.get("duplicate"):
        return JSONResponse(status_code=409, content=result)
    return result


@router.get("/research/{research_id}/async-tasks")
async def list_async_task_records(research_id: str, request: Request):
    await api_state.require_session(request)
    research = await get_research(research_id)
    if not research:
        return JSONResponse(status_code=404, content={"error": "Research not found"})
    return {"items": await list_async_tasks(research_id)}
