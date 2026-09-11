# MAARS Architecture

**English** | [中文版](architecture_cn.md)

MAARS is a four-stage automated research pipeline: from a vague idea to a full paper draft, powered by four AI Agents working in relay.

```
                        Research Director (control plane)
                         /        |         |        \\
User idea -> Refine -> Plan -> Execute -> Paper -> Quality review
              |         |          |          |          |
           evidence   task DAG  validated   draft    revision decision
```

The stage pipeline remains the data plane. `ResearchDirector` is deliberately
read-only: it does not run tools or hide retries. It translates persisted state
into explicit delegation contracts, quality gates, organisation roles, and an
evidence lineage so an interviewer can inspect why the next stage may run.

## Research Control Tower

The detail page has four views which must not be conflated:

| View | Question it answers | Source of truth |
| --- | --- | --- |
| Agent organization | Who reports to and delegates to whom? | Static Director role map |
| Task contracts | What does each lead/worker promise to deliver? | Director snapshot + plan/execution state |
| Execution DAG | What can run in parallel and in what order? | Plan/execution graph |
| Evidence lineage | Which concrete artifacts support the draft and review? | SQLite papers, outputs, literature, reviews |

`GET /api/research/{researchId}/control-tower` returns the Director snapshot.
It contains `qualityGates`, `taskContracts`, `agentOrganization`, and
`evidenceTrail`; the frontend renders them separately from the existing task
DAG workbench.

The four top-level contracts are:

| Stage | Lead | Gate |
| --- | --- | --- |
| Refine | Literature Lead | Keywords and a refined research idea exist |
| Plan | Planning Lead | An executable research plan exists |
| Execute | Execution Lead | Every executable task has a persisted output |
| Paper | Writing Lead | Draft exists and Paper Quality Review has no blockers |

### Paper Quality Review Skill

`paper_agent/skills/paper-quality-review/SKILL.md` is a focused post-drafting
skill. It receives only the draft, plan, and artifact digest; it returns a
structured JSON report instead of silently editing the manuscript. The report
audits claims, methods, citations, reproducibility, findings, and a revision
plan. It is persisted in `paper_reviews`, emitted as `paper-review-complete`,
and can be refreshed with `POST /api/paper/review`.

## Backend

### Layered Structure

```
main.py                         FastAPI + Socket.IO entry point

api/                            Interface layer
  routes/                       13 route modules (idea, plan, execution, paper, research, session, events, ...)
  state.py                      Global session state management
  session_auth.py               HMAC-signed session authentication
  realtime_emitter.py           Socket.IO -> SSE bridge

idea_agent/                     Idea Agent -- literature collection + idea refinement
  agent.py + adk_runner.py      ADK agent mode
  llm/executor.py               LLM single-turn mode
  literature.py + arxiv.py      Literature search (OpenAlex / arXiv)
  __init__.py                   Orchestration (Keywords -> Search -> Refine)

plan_agent/                     Plan Agent -- task decomposition
  agent.py + adk_runner.py      ADK agent mode
  llm/executor.py               LLM single-turn mode
  index.py                      Orchestration (atomicity check -> recursive decomposition -> formatting)
  execution_builder.py          Execution graph construction

task_agent/                     Task Agent -- parallel execution + validation
  runner.py                     ExecutionRunner core class (zero inheritance, ~40 delegate methods)
  runner_deps.py                Dependency injection container (RunnerDeps dataclass)
  runner_retry.py               Retry/attempt pure functions
  runner_memory.py              Execution memory pure functions
  runner_scheduling.py          Scheduling/state/rollback functions
  runner_orchestration.py       Global orchestration loop
  runner_phases.py              Single-task lifecycle phases
  agent.py + adk_runner.py      Docker ADK agent mode
  llm/executor.py               LLM single-turn mode
  llm/validation.py             3-step validation (format gate -> contract review -> original contract)
  pools.py                      Worker concurrency pool
  docker_runtime.py             Docker container lifecycle
  artifact_resolver.py          Inter-task input resolution

paper_agent/                    Paper Agent -- paper draft generation
  runner.py                     Single file (Mock / LLM single-pass / Agent MVP pipeline)
  review.py                     Skill-backed paper quality review runtime
  skills/paper-quality-review/  Review instructions and JSON report schema

orchestrator/                   Research Control Tower control plane
  director.py                   Role map, contracts, gates, evidence lineage snapshot

validate_agent/                 Step-B contract review (Task Agent sub-component)
  executor.py                   Validation criteria adjustment decisions

shared/                         Common infrastructure
  llm_client.py                 Unified LLM client
  constants.py                  Global constants
  adk_runtime.py                Google ADK runtime
  reflection.py                 Self-reflection + skill learning

db/                             SQLite persistence layer
visualization/                  Decomposition tree / execution graph layout computation
```

### Three Modes Per Agent

Every agent supports three execution modes, switched via `api_config`:

| Mode | Use Case | Behavior |
|---|---|---|
| **Mock** | Dev/test | Reads `test/mock-ai/*.json`, simulates streaming |
| **LLM** | Fast execution | Single-turn LLM call via `shared/llm_client.py` |
| **Agent** | Full capability | Google ADK multi-turn tool-use agent |

### Task Agent Internals

The Task Agent is the most complex component. `ExecutionRunner` is a plain class (zero inheritance) that delegates all behavior to 5 function modules via thin wrapper methods:

```
ExecutionRunner
  |-- runner_retry.py          Pure functions, explicit state dict params
  |-- runner_memory.py         Pure functions, state dicts + dep callbacks
  |-- runner_scheduling.py     Pure functions + runner-instance functions
  |-- runner_orchestration.py  Runner-instance functions
  |-- runner_phases.py         Runner-instance functions
```

**Single task lifecycle:**

```
Phase 1: Acquire worker slot
  |
Phase 2: Execute (Docker ADK agent or LLM single-turn)
  |
Phase 3: Validate (3-step)
  Step A: Structural format gate (is output parseable?)
  Step B: Contract review (should validation criteria adjust?)
  Step C: Original contract validation (LLM quality judgment)
  |
Phase 4: Reflect (optional, generate reusable skills)
  |
Phase 5: Finalize (release worker, schedule downstream tasks)
  |  (on validation failure)
  +-> retry_or_fail -> back to Phase 1 (up to 5 attempts)
```

**Dependency injection:** `RunnerDeps` is a dataclass with 25+ injectable callables. Production uses `build_default_deps()`; tests pass `RunnerDeps(xxx=fake)` directly.

## Frontend

Vanilla JavaScript + HTML + CSS, zero external dependencies (aside from CDN-loaded highlight.js).

```
js/
  core/           Foundation (config, state, utils)
  api/            API client (fetch-based, session-aware)
  ws/             SSE connection + maars:* event dispatch
  flows/          Business flow controllers (idea, plan, task, paper, research)
  regions/        Content rendering (output, thinking stream, task tree SVG)
  ui/             UI components (settings modal, sidebar, toast, theme)

css/
  core/           Design tokens, reset, theme palettes (light/dark/black)
  layout/         Page structure
  components/     Shared components (buttons, modal, toast, markdown)
  regions/        Content area styles
  ui/             UI component styles
```

**Data flow:**

```
User action -> js/flows/ -> js/api/ -> HTTP POST -> Backend
Backend processing -> SSE push -> js/ws/websocket.js -> document.dispatchEvent('maars:*')
js/flows/ listens maars:* -> updates state -> js/regions/ renders UI
```

## Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Backend framework | FastAPI + asyncio | Async I/O suits parallel task execution |
| Realtime | SSE (replaced Socket.IO) | Unidirectional push is sufficient, lighter |
| Agent framework | Google ADK | Native tool-use, multi-turn conversation |
| Frontend framework | None (vanilla JS) | Zero dependencies, serve static files directly |
| Styling | Modular CSS + CSS Variables | No build step, multi-theme support |
| DI | RunnerDeps dataclass | Tests inject fakes directly, no monkeypatching |
| Persistence | SQLite | Local-first, zero config |
| Auth | HMAC-signed session + HttpOnly cookie | SSE doesn't support headers; cookies auto-attach |
