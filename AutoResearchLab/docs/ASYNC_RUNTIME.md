# Redis Context + RabbitMQ Worker Runtime

This optional runtime moves long-running research work out of the FastAPI
request process while keeping SQLite and filesystem artifacts as the source of
truth. Redis holds a TTL-bounded context snapshot, RabbitMQ carries only a
small versioned command, and SQLite records the task lifecycle.

## Responsibilities

| Component | Owns | Does not own |
|---|---|---|
| Redis | short-lived context snapshots, idempotency keys | final paper, experiment result, canonical history |
| RabbitMQ | durable commands, bounded retries, dead letters | prompt bodies or large artifacts |
| SQLite/artifacts | task lifecycle, research state and produced artifacts | ephemeral worker coordination |

Messages contain `contextRef`, `artifactRefs`, `traceId`, retry metadata and an
idempotency key. They never contain a full paper, API key or research context.

## Local startup

Docker Desktop must be healthy before starting infrastructure:

```powershell
docker compose -f compose.yaml -f compose.async.yaml up -d redis rabbitmq
$env:MAARS_ASYNC_MODE = "rabbitmq"
$env:MAARS_REDIS_URL = "redis://localhost:6379/0"
$env:MAARS_RABBITMQ_URL = "amqp://maars:change-me-locally@localhost:5672/"
```

For tests and UI exploration without external services, use `MAARS_ASYNC_MODE=memory`.
`memory` is intentionally not a production fallback: production misconfiguration
returns an explicit unavailable error instead of accepting work invisibly.

## API and worker contract

1. Create a research with `POST /api/research`.
2. Queue a stage through `POST /api/research/{researchId}/async-tasks`.
3. Inspect readiness at `GET /api/async-runtime/status` and lifecycle records
   at `GET /api/research/{researchId}/async-tasks`.
4. Run a dedicated worker:

```powershell
$env:MAARS_ASYNC_HANDLER = "async_runtime.worker_adapters:execute"
python -m async_runtime.worker --stage execute
```

Built-in adapters are available for `refine`, `plan`, `execute`, `paper` and
`review`, for example `async_runtime.worker_adapters:plan`. They reload the
live research record and artifacts from SQLite instead of trusting a stale
queue message. Custom adapters must be async functions with signature
`async def handler(envelope, context)`.

## Failure semantics

- Redis `SET NX` rejects duplicate idempotency keys.
- A worker failure increments `attempt`; after `maxAttempts` the message is
  written to `maars.research.dead-letter`.
- If context expires, the worker fails explicitly rather than fabricating a
  context. Rebuild a new snapshot from SQLite/artifacts and dispatch again.
- The next production hardening step is a transactional outbox relay for the
  SQLite-record → RabbitMQ publish gap. The lifecycle record already makes that
  gap observable and recoverable.
