"""Composition root for Redis context, RabbitMQ commands and durable task records."""

from __future__ import annotations

import os
import uuid
from typing import Any

from db import create_async_task, update_async_task

from .broker import InMemoryTaskBroker, RabbitMQTaskBroker
from .context import InMemoryContextStore, RedisContextStore, RuntimeUnavailableError
from .types import AsyncTaskEnvelope, ContextReference


class AsyncResearchRuntime:
    """Dispatches compact, idempotent commands without coupling API and workers."""

    def __init__(self, *, context_store, broker, context_ttl_seconds: int = 24 * 60 * 60) -> None:
        self.context_store = context_store
        self.broker = broker
        self.context_ttl_seconds = max(60, int(context_ttl_seconds))

    @classmethod
    def from_env(cls) -> "AsyncResearchRuntime":
        mode = os.getenv("MAARS_ASYNC_MODE", "disabled").strip().lower()
        if mode == "memory":
            return cls(context_store=InMemoryContextStore(), broker=InMemoryTaskBroker())
        if mode != "rabbitmq":
            raise RuntimeUnavailableError("Async runtime is disabled; set MAARS_ASYNC_MODE=rabbitmq or memory")
        redis_url = os.getenv("MAARS_REDIS_URL", "").strip()
        rabbitmq_url = os.getenv("MAARS_RABBITMQ_URL", "").strip()
        if not redis_url or not rabbitmq_url:
            raise RuntimeUnavailableError("MAARS_REDIS_URL and MAARS_RABBITMQ_URL are required when MAARS_ASYNC_MODE=rabbitmq")
        return cls(
            context_store=RedisContextStore(redis_url, key_prefix=os.getenv("MAARS_REDIS_KEY_PREFIX", "maars")),
            broker=RabbitMQTaskBroker(rabbitmq_url),
            context_ttl_seconds=int(os.getenv("MAARS_CONTEXT_TTL_SECONDS", str(24 * 60 * 60))),
        )

    async def dispatch(
        self,
        *,
        research: dict[str, Any],
        stage: str,
        artifact_refs: list[str] | None = None,
        idempotency_key: str | None = None,
        max_attempts: int = 3,
    ) -> dict[str, Any]:
        research_id = str(research.get("researchId") or "")
        run_id = str(uuid.uuid4())
        ref = ContextReference(research_id=research_id, run_id=run_id, version="v1")
        envelope = AsyncTaskEnvelope.create(
            research_id=research_id,
            run_id=run_id,
            stage=stage,
            context_ref=ref.key,
            artifact_refs=artifact_refs or [],
            idempotency_key=idempotency_key,
            max_attempts=max_attempts,
        )
        claimed = await self.context_store.claim_idempotency(envelope.idempotency_key, self.context_ttl_seconds)
        if not claimed:
            return {"duplicate": True, "idempotencyKey": envelope.idempotency_key}
        context = {
            "schemaVersion": "v1",
            "research": research,
            "stage": envelope.stage,
            "artifactRefs": list(envelope.artifact_refs),
            "traceId": envelope.trace_id,
        }
        try:
            await self.context_store.put(ref, context, self.context_ttl_seconds)
            record = await create_async_task({**envelope.to_dict(), "status": "queued"})
            if record.get("taskId") != envelope.task_id:
                return {"duplicate": True, "task": record}
            await self.broker.publish(envelope)
        except Exception:
            await self.context_store.delete(ref.key)
            await self.context_store.release_idempotency(envelope.idempotency_key)
            raise
        return {"duplicate": False, "task": {**envelope.to_dict(), "status": "queued"}}

    async def consume_once(self, stage: str, handler) -> bool:
        async def tracked_handler(envelope: AsyncTaskEnvelope) -> None:
            await update_async_task(envelope.task_id, status="running", attempt=envelope.attempt, error="")
            try:
                context = await self.context_store.get(envelope.context_ref)
                if context is None:
                    raise RuntimeError("Context snapshot expired; rebuild it from durable artifacts before retrying")
                await handler(envelope, context)
            except Exception as exc:
                await update_async_task(envelope.task_id, status="failed", attempt=envelope.attempt + 1, error=str(exc)[:1024])
                raise
            await update_async_task(envelope.task_id, status="completed", attempt=envelope.attempt, error="")

        return await self.broker.consume_once(stage, tracked_handler)

    async def health(self) -> dict[str, Any]:
        context = await self.context_store.health()
        broker = await self.broker.health()
        return {"ready": bool(context.get("ready") and broker.get("ready")), "context": context, "broker": broker}

    async def close(self) -> None:
        await self.context_store.close()
        await self.broker.close()
