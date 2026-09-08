"""Helpers for research route stage validation and execution-step event loading."""

import json
from pathlib import Path

from db import (
    find_execution_run_ids_for_research,
    get_execution,
    get_execution_step_root_dir,
    get_idea,
    get_paper,
    get_plan,
    list_plan_outputs,
)
from plan_agent.execution_builder import build_execution_from_plan
from shared.idea_utils import get_idea_text


def _run_sort_key(run_id: str) -> tuple[int, str]:
    s = str(run_id or "").strip()
    if s.startswith("exec_"):
        suffix = s.split("exec_", 1)[1]
        if suffix.isdigit():
            return (int(suffix), s)
    return (0, s)


def _load_latest_step_events(idea_id: str | None, plan_id: str | None, *, max_events: int = 2000) -> dict:
    run_ids = find_execution_run_ids_for_research(idea_id, plan_id)
    if not run_ids:
        return {"runId": "", "events": []}

    events_limit = max(100, int(max_events or 2000))
    sorted_run_ids = sorted(run_ids, key=_run_sort_key, reverse=True)
    for run_id in sorted_run_ids:
        try:
            step_root = get_execution_step_root_dir(run_id)
        except Exception:
            continue
        if not step_root.exists() or not step_root.is_dir():
            continue

        items: list[dict] = []
        for step_file in sorted(step_root.glob("*/events.jsonl")):
            task_id = step_file.parent.name
            if not task_id:
                continue
            try:
                with Path(step_file).open("r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        raw = (line or "").strip()
                        if not raw:
                            continue
                        try:
                            record = json.loads(raw)
                        except Exception:
                            continue
                        event_name = str(record.get("event") or "").strip()
                        if not event_name:
                            continue
                        items.append(
                            {
                                "ts": int(record.get("ts") or 0),
                                "taskId": str(record.get("taskId") or task_id),
                                "event": event_name,
                                "payload": record.get("payload") or {},
                            }
                        )
            except Exception:
                continue

        if not items:
            continue

        items.sort(key=lambda x: (int(x.get("ts") or 0), str(x.get("taskId") or "")))
        if len(items) > events_limit:
            items = items[-events_limit:]
        return {"runId": run_id, "events": items}

    return {"runId": sorted_run_ids[0], "events": []}


def _stage_rank(stage: str) -> int:
    order = {"refine": 0, "plan": 1, "execute": 2, "paper": 3}
    return order.get((stage or "").strip().lower(), 0)


def _normalize_stage(stage: str) -> str:
    s = (stage or "").strip().lower()
    return s if s in ("refine", "plan", "execute", "paper") else "refine"


async def _validate_refine_completion(idea_id: str | None) -> tuple[bool, str | None]:
    idea = str(idea_id or "").strip()
    if not idea:
        return False, "refine has no idea artifact"
    idea_data = await get_idea(idea)
    if not idea_data:
        return False, "refine idea artifact is missing"
    if not get_idea_text(idea_data.get("refined_idea")):
        return False, "refine produced no refined idea"
    return True, None


async def _validate_plan_completion(idea_id: str | None, plan_id: str | None) -> tuple[bool, str | None]:
    idea = str(idea_id or "").strip()
    plan = str(plan_id or "").strip()
    if not idea or not plan:
        return False, "plan has no plan artifact"
    plan_data = await get_plan(idea, plan)
    if not plan_data or not (plan_data.get("tasks") or []):
        return False, "plan artifact is missing or empty"
    execution = build_execution_from_plan(plan_data)
    if not (execution.get("tasks") or []):
        return False, "plan produced no executable atomic tasks"
    return True, None


async def _validate_execute_completion(idea_id: str | None, plan_id: str | None) -> tuple[bool, str | None]:
    idea = str(idea_id or "").strip()
    plan = str(plan_id or "").strip()
    if not idea or not plan:
        return False, "execute has no execution artifact"
    execution = await get_execution(idea, plan)
    execution_tasks = (execution or {}).get("tasks") or []
    if not execution_tasks:
        return False, "execution artifact is missing or empty"
    outputs = await list_plan_outputs(idea, plan)
    missing = [t.get("task_id") for t in execution_tasks if t.get("task_id") and t.get("task_id") not in outputs]
    if missing:
        return False, f"execution is missing persisted outputs for {len(missing)} task(s)"
    return True, None


async def _validate_paper_completion(idea_id: str | None, plan_id: str | None) -> tuple[bool, str | None]:
    idea = str(idea_id or "").strip()
    plan = str(plan_id or "").strip()
    if not idea or not plan:
        return False, "paper has no paper artifact"
    paper = await get_paper(idea, plan)
    if not paper or not str(paper.get("content") or "").strip():
        return False, "paper artifact is missing or empty"
    return True, None


async def _validate_stage_completion(research: dict | None, stage: str) -> tuple[bool, str | None]:
    r = research or {}
    idea_id = r.get("currentIdeaId")
    plan_id = r.get("currentPlanId")
    s = _normalize_stage(stage)
    if s == "refine":
        return await _validate_refine_completion(idea_id)
    if s == "plan":
        return await _validate_plan_completion(idea_id, plan_id)
    if s == "execute":
        return await _validate_execute_completion(idea_id, plan_id)
    if s == "paper":
        return await _validate_paper_completion(idea_id, plan_id)
    return False, f"unknown stage '{s}'"


async def _check_stage_prerequisites(research: dict | None, target_stage: str) -> str | None:
    """Return error message if target stage cannot start because predecessors are not truly completed."""
    stage = _normalize_stage(target_stage)
    order = ["refine", "plan", "execute", "paper"]
    target_rank = _stage_rank(stage)
    if target_rank <= 0:
        return None

    current_stage = _normalize_stage(str((research or {}).get("stage") or "refine"))
    current_status = str((research or {}).get("stageStatus") or "idle").strip().lower() or "idle"
    for need_stage in order[:target_rank]:
        valid, reason = await _validate_stage_completion(research, need_stage)
        if not valid:
            return f"Cannot start '{stage}': prerequisite '{need_stage}' is not completed ({reason or 'missing artifact'})"
    if current_stage == stage and current_status == "running":
        return f"Stage '{stage}' is already running"
    return None
