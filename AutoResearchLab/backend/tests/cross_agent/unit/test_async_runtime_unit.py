import anyio

from async_runtime.broker import InMemoryTaskBroker
from async_runtime.coordinator import AsyncResearchCoordinator
from async_runtime.context import InMemoryContextStore
from async_runtime.runtime import AsyncResearchRuntime
from async_runtime.types import ContextReference
from db import create_research, get_async_task, get_research, list_async_tasks, save_idea, update_research_stage


async def _dispatch_and_consume() -> None:
    store = InMemoryContextStore()
    broker = InMemoryTaskBroker()
    runtime = AsyncResearchRuntime(context_store=store, broker=broker)
    research = {"researchId": "research_async_1", "prompt": "test", "stage": "execute"}

    result = await runtime.dispatch(
        research=research,
        stage="execute",
        artifact_refs=["artifact:plan:v1"],
        idempotency_key="research_async_1:execute:v1",
    )
    assert result["duplicate"] is False
    task = result["task"]
    assert task["contextRef"].startswith("research:research_async_1:run:")
    assert "prompt" not in task  # RabbitMQ command stays compact.
    assert await store.get(task["contextRef"])

    seen = {}

    async def handler(envelope, context):
        seen["taskId"] = envelope.task_id
        seen["context"] = context

    assert await runtime.consume_once("execute", handler) is True
    assert seen["taskId"] == task["taskId"]
    assert seen["context"]["research"]["researchId"] == "research_async_1"
    record = await get_async_task(task["taskId"])
    assert record["status"] == "completed"
    assert record["artifactRefs"] == ["artifact:plan:v1"]


def test_dispatch_persists_context_and_tracks_completion():
    anyio.run(_dispatch_and_consume)


async def _duplicate_is_idempotent() -> None:
    runtime = AsyncResearchRuntime(context_store=InMemoryContextStore(), broker=InMemoryTaskBroker())
    research = {"researchId": "research_async_2", "prompt": "test"}
    first = await runtime.dispatch(research=research, stage="plan", idempotency_key="same-key")
    second = await runtime.dispatch(research=research, stage="plan", idempotency_key="same-key")
    assert first["duplicate"] is False
    assert second == {"duplicate": True, "idempotencyKey": "same-key"}


def test_dispatch_is_idempotent():
    anyio.run(_duplicate_is_idempotent)


async def _failed_work_is_retried_then_dead_lettered() -> None:
    broker = InMemoryTaskBroker()
    runtime = AsyncResearchRuntime(context_store=InMemoryContextStore(), broker=broker)
    result = await runtime.dispatch(
        research={"researchId": "research_async_3", "prompt": "test"},
        stage="execute",
        idempotency_key="research_async_3:execute",
        max_attempts=2,
    )
    task_id = result["task"]["taskId"]

    async def fail(*_args):
        raise RuntimeError("simulated worker failure")

    assert await runtime.consume_once("execute", fail) is True
    assert await runtime.consume_once("execute", fail) is True
    assert len(broker.dead_letters) == 1
    record = await get_async_task(task_id)
    assert record["status"] == "failed"
    assert record["attempt"] == 2
    assert "simulated worker failure" in record["error"]


def test_failed_work_retries_then_dead_letters():
    anyio.run(_failed_work_is_retried_then_dead_lettered)


def test_context_reference_round_trip():
    ref = ContextReference(research_id="research_1", run_id="run_1", version="v1")
    assert ContextReference.parse(ref.key) == ref


async def _director_handoff_after_passing_gate() -> None:
    runtime = AsyncResearchRuntime(context_store=InMemoryContextStore(), broker=InMemoryTaskBroker())
    coordinator = AsyncResearchCoordinator(runtime)
    research_id = "research_director_handoff"
    idea_id = "idea_director_handoff"
    await create_research(research_id, "test", "Director handoff")
    await save_idea(
        {"idea": "test", "keywords": ["agent"], "papers": [], "refined_idea": "A testable question."},
        idea_id,
    )
    await update_research_stage(research_id, stage="refine", stage_status="completed", current_idea_id=idea_id)
    research = await get_research(research_id)
    dispatched = await runtime.dispatch(research=research, stage="refine", idempotency_key="director-handoff-refine")

    async def completed(_envelope, _context):
        return None

    assert await runtime.consume_once(
        "refine", completed, on_completed=lambda envelope, _context: coordinator.advance_after_completion(envelope)
    ) is True
    tasks = await list_async_tasks(research_id)
    assert any(item["stage"] == "plan" and item["status"] == "queued" for item in tasks)


def test_director_queues_next_stage_only_after_gate_passes():
    anyio.run(_director_handoff_after_passing_gate)
