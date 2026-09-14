"""Director-owned handoff between independently deployed research workers.

Workers execute exactly one stage. Once its persisted artifacts satisfy the
Director quality gate, this coordinator publishes the next compact command.
It intentionally has no dependency on a browser session or FastAPI memory.
"""

from __future__ import annotations

from typing import Any

from db import (
    get_execution, get_idea, get_paper, get_paper_review, get_plan,
    get_research, list_async_tasks, list_plan_outputs, update_research_stage,
)
from orchestrator import ResearchDirector

from .types import AsyncTaskEnvelope


NEXT_STAGE = {"refine": "plan", "plan": "execute", "execute": "paper"}


class AsyncResearchCoordinator:
    """Queue stages and let the Research Director decide whether to advance."""

    def __init__(self, runtime, director: ResearchDirector | None = None) -> None:
        self.runtime = runtime
        self.director = director or ResearchDirector()

    async def queue_stage(
        self, research: dict[str, Any], stage: str, *, artifact_refs: list[str] | None = None,
        max_attempts: int = 3,
    ) -> dict[str, Any]:
        research_id = str(research.get("researchId") or "")
        normalized = str(stage or "").strip().lower()
        if not research_id:
            raise ValueError("researchId is required")
        existing = next(
            (item for item in await list_async_tasks(research_id)
             if item.get("stage") == normalized and item.get("status") in {"queued", "running"}),
            None,
        )
        if existing:
            return {"duplicate": True, "task": existing, "reason": "stage already queued or running"}
        result = await self.runtime.dispatch(
            research=research, stage=normalized, artifact_refs=artifact_refs or [], max_attempts=max_attempts,
        )
        if not result.get("duplicate"):
            await update_research_stage(research_id, stage=normalized, stage_status="queued")
        return result

    async def snapshot(self, research_id: str) -> dict[str, Any] | None:
        research = await get_research(research_id)
        if not research:
            return None
        idea_id, plan_id = research.get("currentIdeaId"), research.get("currentPlanId")
        idea = await get_idea(idea_id) if idea_id else None
        plan = await get_plan(idea_id, plan_id) if idea_id and plan_id else None
        execution = await get_execution(idea_id, plan_id) if idea_id and plan_id else None
        outputs = await list_plan_outputs(idea_id, plan_id) if idea_id and plan_id else {}
        paper = await get_paper(idea_id, plan_id) if idea_id and plan_id else None
        paper_review = await get_paper_review(idea_id, plan_id) if idea_id and plan_id else None
        return self.director.snapshot(
            research=research, idea=idea, plan=plan, execution=execution, outputs=outputs,
            paper=paper, paper_review=paper_review,
        )

    async def advance_after_completion(self, envelope: AsyncTaskEnvelope) -> dict[str, Any]:
        """Advance exactly once and only when the completed stage's gate passes."""
        research = await get_research(envelope.research_id)
        if not research:
            return {"advanced": False, "reason": "research deleted"}
        snapshot = await self.snapshot(envelope.research_id)
        gate_status = {
            str(gate.get("stage")): str(gate.get("status"))
            for gate in (snapshot or {}).get("qualityGates", [])
        }
        status = gate_status.get(envelope.stage, "pending")
        if status != "passed":
            terminal = "needs_revision" if status == "needs_revision" else "failed"
            await update_research_stage(
                envelope.research_id, stage=envelope.stage, stage_status=terminal,
                error=f"Director quality gate for {envelope.stage} is {status}",
            )
            return {"advanced": False, "gateStatus": status, "reason": "quality gate not passed"}
        next_stage = NEXT_STAGE.get(envelope.stage)
        if not next_stage:
            return {"advanced": False, "gateStatus": status, "reason": "terminal stage completed"}
        result = await self.queue_stage(research, next_stage)
        return {"advanced": not result.get("duplicate"), "nextStage": next_stage, "task": result.get("task")}

    async def mark_failed(self, envelope: AsyncTaskEnvelope, error: Exception) -> None:
        await update_research_stage(
            envelope.research_id, stage=envelope.stage, stage_status="failed", error=str(error)[:1024],
        )
