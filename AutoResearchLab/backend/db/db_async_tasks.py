"""Durable lifecycle records for RabbitMQ-dispatched research tasks.

RabbitMQ is deliberately not the system of record.  This small outbox-like
record lets the API expose a task's lifecycle and makes a duplicate publish
visible rather than silently running work twice.
"""

from __future__ import annotations

from . import sqlite_backend as base


async def create_async_task(record: dict) -> dict:
    """Create one queued task record, returning an existing idempotent record."""
    now = base._now()
    async with base._db() as db:
        try:
            await db.execute(
                """
                INSERT INTO async_tasks(
                    task_id,research_id,run_id,stage,status,context_ref,artifact_refs,
                    idempotency_key,trace_id,attempt,max_attempts,error,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    record["taskId"], record["researchId"], record["runId"], record["stage"],
                    record.get("status", "queued"), record["contextRef"],
                    base._json_dumps(record.get("artifactRefs") or []), record["idempotencyKey"],
                    record["traceId"], int(record.get("attempt", 0)), int(record.get("maxAttempts", 3)),
                    record.get("error"), now, now,
                ),
            )
            await db.commit()
        except Exception:
            async with db.execute(
                "SELECT * FROM async_tasks WHERE idempotency_key = ?", (record["idempotencyKey"],)
            ) as cur:
                row = await cur.fetchone()
            if row is None:
                raise
            return _row_to_dict(row)
    return {**record, "status": record.get("status", "queued"), "createdAt": now, "updatedAt": now}


async def get_async_task(task_id: str) -> dict | None:
    async with base._db() as db:
        async with db.execute("SELECT * FROM async_tasks WHERE task_id = ?", (task_id,)) as cur:
            row = await cur.fetchone()
    return _row_to_dict(row) if row else None


async def update_async_task(task_id: str, *, status: str, attempt: int | None = None, error: str | None = None) -> None:
    fields = ["status = ?", "updated_at = ?"]
    params: list[object] = [status, base._now()]
    if attempt is not None:
        fields.append("attempt = ?")
        params.append(int(attempt))
    if error is not None:
        fields.append("error = ?")
        params.append(error)
    params.append(task_id)
    async with base._db() as db:
        await db.execute(f"UPDATE async_tasks SET {', '.join(fields)} WHERE task_id = ?", params)
        await db.commit()


async def list_async_tasks(research_id: str) -> list[dict]:
    async with base._db() as db:
        async with db.execute(
            "SELECT * FROM async_tasks WHERE research_id = ? ORDER BY created_at DESC", (research_id,)
        ) as cur:
            rows = await cur.fetchall()
    return [_row_to_dict(row) for row in rows]


def _row_to_dict(row) -> dict:
    return {
        "taskId": row["task_id"],
        "researchId": row["research_id"],
        "runId": row["run_id"],
        "stage": row["stage"],
        "status": row["status"],
        "contextRef": row["context_ref"],
        "artifactRefs": base._json_loads(row["artifact_refs"]) or [],
        "idempotencyKey": row["idempotency_key"],
        "traceId": row["trace_id"],
        "attempt": int(row["attempt"]),
        "maxAttempts": int(row["max_attempts"]),
        "error": row["error"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }
