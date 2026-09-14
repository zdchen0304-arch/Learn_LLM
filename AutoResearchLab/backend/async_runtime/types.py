"""Versioned, small message contracts for asynchronous research tasks."""

from __future__ import annotations

from dataclasses import dataclass, replace
import time
import uuid
from typing import Any


VALID_STAGES = frozenset({"refine", "plan", "execute", "paper", "review"})


@dataclass(frozen=True)
class ContextReference:
    """Points to a Redis context snapshot; payloads never travel in RabbitMQ."""

    research_id: str
    run_id: str
    version: str

    @property
    def key(self) -> str:
        return f"research:{self.research_id}:run:{self.run_id}:context:{self.version}"

    @classmethod
    def parse(cls, value: str) -> "ContextReference":
        parts = str(value or "").split(":")
        if len(parts) != 6 or parts[0] != "research" or parts[2] != "run" or parts[4] != "context":
            raise ValueError("context_ref has an invalid format")
        return cls(research_id=parts[1], run_id=parts[3], version=parts[5])


@dataclass(frozen=True)
class AsyncTaskEnvelope:
    """A durable command envelope; deliberately excludes research body text."""

    task_id: str
    research_id: str
    run_id: str
    stage: str
    context_ref: str
    artifact_refs: tuple[str, ...]
    idempotency_key: str
    trace_id: str
    attempt: int = 0
    max_attempts: int = 3
    event_type: str = "research.task.execute"
    schema_version: str = "v1"
    created_at: float = 0.0

    @classmethod
    def create(
        cls,
        *,
        research_id: str,
        run_id: str,
        stage: str,
        context_ref: str,
        artifact_refs: list[str] | tuple[str, ...] = (),
        idempotency_key: str | None = None,
        max_attempts: int = 3,
    ) -> "AsyncTaskEnvelope":
        normalized_stage = str(stage or "").lower()
        if normalized_stage not in VALID_STAGES:
            raise ValueError(f"Unsupported async stage: {stage}")
        if not research_id or not run_id:
            raise ValueError("research_id and run_id are required")
        ContextReference.parse(context_ref)
        task_id = str(uuid.uuid4())
        return cls(
            task_id=task_id,
            research_id=research_id,
            run_id=run_id,
            stage=normalized_stage,
            context_ref=context_ref,
            artifact_refs=tuple(str(item) for item in artifact_refs if str(item)),
            idempotency_key=idempotency_key or f"{research_id}:{run_id}:{normalized_stage}",
            trace_id=str(uuid.uuid4()),
            max_attempts=max(1, min(int(max_attempts), 10)),
            created_at=time.time(),
        )

    def next_attempt(self) -> "AsyncTaskEnvelope":
        return replace(self, attempt=self.attempt + 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "eventType": self.event_type,
            "taskId": self.task_id,
            "researchId": self.research_id,
            "runId": self.run_id,
            "stage": self.stage,
            "contextRef": self.context_ref,
            "artifactRefs": list(self.artifact_refs),
            "idempotencyKey": self.idempotency_key,
            "traceId": self.trace_id,
            "attempt": self.attempt,
            "maxAttempts": self.max_attempts,
            "createdAt": self.created_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AsyncTaskEnvelope":
        if payload.get("schemaVersion") != "v1" or payload.get("eventType") != "research.task.execute":
            raise ValueError("Unsupported async task schema")
        return cls(
            task_id=str(payload["taskId"]),
            research_id=str(payload["researchId"]),
            run_id=str(payload["runId"]),
            stage=str(payload["stage"]).lower(),
            context_ref=str(payload["contextRef"]),
            artifact_refs=tuple(str(item) for item in (payload.get("artifactRefs") or [])),
            idempotency_key=str(payload["idempotencyKey"]),
            trace_id=str(payload["traceId"]),
            attempt=int(payload.get("attempt", 0)),
            max_attempts=int(payload.get("maxAttempts", 3)),
            event_type=str(payload.get("eventType")),
            schema_version=str(payload.get("schemaVersion")),
            created_at=float(payload.get("createdAt", 0)),
        )
