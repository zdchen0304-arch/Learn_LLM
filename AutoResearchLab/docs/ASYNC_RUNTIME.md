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
docker compose -f compose.yaml -f compose.async.yaml up -d --build
```

This starts FastAPI, Redis, RabbitMQ and one restartable consumer for each
stage. The browser can select `sync` or `async`; async runs survive a browser
refresh because their state is persisted outside the API process.

For tests and UI exploration without external services, use `MAARS_ASYNC_MODE=memory`.
`memory` is intentionally not a production fallback: production misconfiguration
returns an explicit unavailable error instead of accepting work invisibly.

## API and worker contract

1. Create a research with `POST /api/research`.
2. Queue a stage through `POST /api/research/{researchId}/async-tasks`.
3. Inspect readiness at `GET /api/async-runtime/status` and lifecycle records
   at `GET /api/research/{researchId}/async-tasks`.
4. Compose runs dedicated workers automatically (`maars-worker-refine`, `plan`,
   `execute`, `paper`, `review`). Each uses an adapter with signature:

Built-in adapters reload the
live research record and artifacts from SQLite instead of trusting a stale
queue message. Custom adapters must be async functions with signature
`async def handler(envelope, context)`.

After a worker completes, `AsyncResearchCoordinator` builds a
`ResearchDirector` snapshot from persisted artifacts. It queues the next stage
only when that stage's upstream quality gate is `passed`; a failed gate is
recorded as `failed` or `needs_revision` instead of being bypassed.

## Real infrastructure smoke test

After the containers are healthy, this test verifies a Redis context write,
RabbitMQ publish/consume round trip, and SQLite lifecycle update without
calling an LLM:

```powershell
docker compose -f compose.yaml -f compose.async.yaml exec -T maars-api pytest tests/cross_agent/integration/test_real_async_runtime.py -q
```

## Failure semantics

- Redis `SET NX` rejects duplicate idempotency keys.
- A worker failure increments `attempt`; after `maxAttempts` the message is
  written to `maars.research.dead-letter`.
- If context expires, the worker fails explicitly rather than fabricating a
  context. Rebuild a new snapshot from SQLite/artifacts and dispatch again.
- The next production hardening step is a transactional outbox relay for the
  SQLite-record → RabbitMQ publish gap. The lifecycle record already makes that
  gap observable and recoverable.
