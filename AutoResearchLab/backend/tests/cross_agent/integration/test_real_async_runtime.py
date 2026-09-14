"""Opt-in smoke test against real Redis and RabbitMQ services.

Run only when MAARS_ASYNC_MODE=rabbitmq.  It uses a no-op handler so no model
provider, Docker task sandbox or external literature service is required.
"""

import os
import uuid

import pytest


pytestmark = pytest.mark.asyncio


@pytest.mark.skipif(
    os.getenv("MAARS_ASYNC_MODE", "").lower() != "rabbitmq",
    reason="requires MAARS_ASYNC_MODE=rabbitmq and live local infrastructure",
)
async def test_real_redis_context_and_rabbitmq_command_round_trip():
    from async_runtime import AsyncResearchRuntime
    from db import create_research, delete_research_cascade, get_async_task, get_research

    research_id = f"integration_async_{uuid.uuid4().hex[:12]}"
    runtime = AsyncResearchRuntime.from_env()
    task_id = ""
    task = None
    try:
        await create_research(research_id, "integration smoke test", "async integration smoke")
        research = await get_research(research_id)
        result = await runtime.dispatch(
            research=research,
            stage="review",
            idempotency_key=f"{research_id}:review",
            max_attempts=2,
        )
        assert result["duplicate"] is False
        task = result["task"]
        task_id = task["taskId"]
        observed = {}

        async def handler(envelope, context):
            observed["taskId"] = envelope.task_id
            observed["researchId"] = context["research"]["researchId"]

        assert await runtime.consume_once("review", handler) is True
        assert observed == {"taskId": task_id, "researchId": research_id}
        persisted = await get_async_task(task_id)
        assert persisted["status"] == "completed"
    finally:
        if task:
            await runtime.context_store.delete(task["contextRef"])
            await runtime.context_store.release_idempotency(task["idempotencyKey"])
        await runtime.close()
        await delete_research_cascade(research_id)
    assert await get_async_task(task_id) is None
