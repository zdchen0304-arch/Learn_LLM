"""Research API - Product-level unit (Research) that runs the full pipeline.

Research is the primary unit of work. It links to the latest ideaId and planId
created during the pipeline runs.

Pipeline stages: refine -> plan -> execute -> paper
"""

import time
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from db import (
    create_research,
    delete_research_cascade,
    get_execution,
    get_idea,
    get_paper,
    get_plan,
    get_research,
    list_plan_outputs,
    list_researches,
)

from .. import state as api_state
from ..schemas import ResearchCreateRequest
from .research_helpers import _load_latest_step_events
from .research_pipeline import _cancel_research_running_tasks
from .research_run_routes import router as research_run_router

router = APIRouter()


def _make_research_id() -> str:
    return f"research_{int(time.time() * 1000)}"


def _make_title(prompt: str) -> str:
    s = (prompt or "").strip().replace("\n", " ")
    s = " ".join(s.split())
    if not s:
        return "Untitled"
    return s[:64]


@router.get("")
async def list_researches_route(request: Request):
    await api_state.require_session(request)
    items = await list_researches()
    return {"items": items}


@router.post("")
async def create_research_route(body: ResearchCreateRequest, request: Request):
    await api_state.require_session(request)
    prompt = (body.prompt or "").strip()
    if not prompt:
        return JSONResponse(status_code=400, content={"error": "prompt is required"})
    research_id = _make_research_id()
    await create_research(research_id, prompt, _make_title(prompt))
    return {"researchId": research_id}


@router.get("/{research_id}")
async def get_research_route(research_id: str, request: Request):
    await api_state.require_session(request)
    research = await get_research(research_id)
    if not research:
        return JSONResponse(status_code=404, content={"error": "Research not found"})
    idea_id = research.get("currentIdeaId")
    plan_id = research.get("currentPlanId")

    idea = await get_idea(idea_id) if idea_id else None
    plan = await get_plan(idea_id, plan_id) if (idea_id and plan_id) else None
    execution = await get_execution(idea_id, plan_id) if (idea_id and plan_id) else None
    outputs = await list_plan_outputs(idea_id, plan_id) if (idea_id and plan_id) else {}
    paper = await get_paper(idea_id, plan_id) if (idea_id and plan_id) else None
    step_events = _load_latest_step_events(idea_id, plan_id) if (idea_id and plan_id) else {"runId": "", "events": []}

    return {
        "research": research,
        "idea": idea,
        "plan": plan,
        "execution": execution,
        "outputs": outputs,
        "paper": paper,
        "stepEvents": step_events,
    }


@router.delete("/{research_id}")
async def delete_research_route(research_id: str, request: Request):
    await api_state.require_session(request)
    research = await get_research(research_id)
    if not research:
        return JSONResponse(status_code=404, content={"error": "Research not found"})

    await _cancel_research_running_tasks(research_id, api_state.sessions)

    await delete_research_cascade(research_id)
    return {"success": True, "researchId": research_id}


router.include_router(research_run_router, prefix="/{research_id}")
