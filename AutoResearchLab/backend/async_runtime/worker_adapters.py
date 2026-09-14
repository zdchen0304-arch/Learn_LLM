"""Stage adapters that let a detached worker reuse the persisted MAARS pipeline.

Each adapter reloads research state from SQLite instead of trusting a stale
message body.  Realtime browser events remain an API-process concern; workers
report their lifecycle through ``async_tasks`` so the UI can poll safely.
"""

from __future__ import annotations

import time

from db import (
    get_effective_config,
    get_paper,
    get_plan,
    get_research,
    list_plan_outputs,
    save_paper_review,
)
from paper_agent.review import review_paper

from .types import AsyncTaskEnvelope


async def _live_research(envelope: AsyncTaskEnvelope) -> dict:
    research = await get_research(envelope.research_id)
    if not research:
        raise ValueError(f"Research not found: {envelope.research_id}")
    return research


async def _worker_session(envelope: AsyncTaskEnvelope):
    # A worker must never depend on a browser session being resident in memory.
    from api import state as api_state

    return await api_state.get_or_create_session_state(f"worker-{envelope.trace_id}")


async def refine(envelope: AsyncTaskEnvelope, _context: dict) -> None:
    from api.routes.research_pipeline import _run_stage_refine

    research = await _live_research(envelope)
    prompt = str(research.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("Research prompt is empty")
    idea_id = str(research.get("currentIdeaId") or f"idea_{int(time.time() * 1000)}")
    session_id = f"worker-{envelope.trace_id}"
    session = await _worker_session(envelope)
    await _run_stage_refine(session_id, session, envelope.research_id, prompt, idea_id)


async def plan(envelope: AsyncTaskEnvelope, _context: dict) -> None:
    from api.routes.research_pipeline import _run_stage_plan

    research = await _live_research(envelope)
    idea_id = str(research.get("currentIdeaId") or "")
    if not idea_id:
        raise ValueError("Plan worker requires a completed refine stage")
    plan_id = str(research.get("currentPlanId") or f"plan_{int(time.time() * 1000)}")
    session_id = f"worker-{envelope.trace_id}"
    session = await _worker_session(envelope)
    await _run_stage_plan(session_id, session, envelope.research_id, idea_id, plan_id)


async def execute(envelope: AsyncTaskEnvelope, _context: dict) -> None:
    from api.routes.research_pipeline import _run_stage_execute

    research = await _live_research(envelope)
    idea_id = str(research.get("currentIdeaId") or "")
    plan_id = str(research.get("currentPlanId") or "")
    if not idea_id or not plan_id:
        raise ValueError("Execution worker requires persisted idea and plan IDs")
    session_id = f"worker-{envelope.trace_id}"
    session = await _worker_session(envelope)
    await _run_stage_execute(session_id, session, envelope.research_id, idea_id, plan_id)


async def paper(envelope: AsyncTaskEnvelope, _context: dict) -> None:
    from api.routes.research_pipeline import _run_stage_paper

    research = await _live_research(envelope)
    idea_id = str(research.get("currentIdeaId") or "")
    plan_id = str(research.get("currentPlanId") or "")
    if not idea_id or not plan_id:
        raise ValueError("Paper worker requires persisted idea and plan IDs")
    session_id = f"worker-{envelope.trace_id}"
    session = await _worker_session(envelope)
    await _run_stage_paper(session_id, session, envelope.research_id, idea_id, plan_id, "markdown")


async def review(envelope: AsyncTaskEnvelope, _context: dict) -> None:
    research = await _live_research(envelope)
    idea_id = str(research.get("currentIdeaId") or "")
    plan_id = str(research.get("currentPlanId") or "")
    if not idea_id or not plan_id:
        raise ValueError("Review worker requires persisted idea and plan IDs")
    paper_doc = await get_paper(idea_id, plan_id)
    if not paper_doc:
        raise ValueError("Review worker requires a persisted paper draft")
    review_result = await review_paper(
        content=str(paper_doc.get("content") or ""),
        plan=await get_plan(idea_id, plan_id) or {},
        outputs=await list_plan_outputs(idea_id, plan_id),
        api_config=await get_effective_config(),
    )
    await save_paper_review(idea_id, plan_id, review_result)
