import asyncio

import anyio

from task_agent.runner import ExecutionRunner
from task_agent.runner_deps import RunnerDeps


async def _run_rollback_keeps_upstream():
    released = []

    def fake_release(task_id):
        released.append(task_id)
        return task_id

    deps = RunnerDeps(release_worker=fake_release)
    runner = ExecutionRunner(sio=None, session_id="test", deps=deps)

    task_1_1 = {"task_id": "1_1", "dependencies": [], "status": "done"}
    task_1_2 = {"task_id": "1_2", "dependencies": ["1_1"], "status": "execution-failed"}
    task_1_3 = {"task_id": "1_3", "dependencies": ["1_2"], "status": "undone"}

    runner.task_map = {
        "1_1": task_1_1,
        "1_2": task_1_2,
        "1_3": task_1_3,
    }
    runner.reverse_dependency_index = {
        "1_1": ["1_2"],
        "1_2": ["1_3"],
        "1_3": [],
    }

    runner.completed_tasks = {"1_1"}
    runner.pending_tasks = {"1_2", "1_3"}
    runner.running_tasks = set()

    await runner._rollback_task(task_1_2)

    assert "1_1" in runner.completed_tasks
    assert runner.task_map["1_1"]["status"] == "done"
    assert "1_1" not in runner.pending_tasks

    assert runner.task_map["1_2"]["status"] == "undone"
    assert runner.task_map["1_3"]["status"] == "undone"
    assert "1_2" in runner.pending_tasks
    assert "1_3" in runner.pending_tasks

    assert "1_2" in released
    assert "1_3" in released
    assert "1_1" not in released


def test_rollback_only_resets_failed_and_downstream():
    anyio.run(_run_rollback_keeps_upstream)


async def _run_handle_task_error_emits_event():
    deps = RunnerDeps(release_worker=lambda _task_id: None)
    runner = ExecutionRunner(sio=None, session_id="test", deps=deps)
    runner.task_map = {"1_1": {"task_id": "1_1", "status": "doing"}}
    runner.reverse_dependency_index = {"1_1": []}
    runner.completed_tasks = set()
    runner.running_tasks = {"1_1"}
    runner.pending_tasks = {"1_1"}

    emitted = []

    def fake_emit(event, data):
        emitted.append((event, data))

    runner._emit = fake_emit

    await runner._handle_task_error({"task_id": "1_1"}, RuntimeError("boom"))

    task_error = [payload for event, payload in emitted if event == "task-error"]
    assert task_error, "Expected task-error event to be emitted"
    assert task_error[0].get("taskId") == "1_1"
    assert task_error[0].get("willRetry") is False
    assert "boom" in str(task_error[0].get("error"))


def test_handle_task_error_emits_task_error_event():
    anyio.run(_run_handle_task_error_emits_event)


async def _run_build_context_with_retry_memory():
    deps = RunnerDeps()
    runner = ExecutionRunner(sio=None, session_id="test", deps=deps)
    runner.execution_run_id = "exec_x"
    runner._idea_text = "global objective"
    runner.chain_cache = [
        {"task_id": "1_1", "status": "doing"},
        {"task_id": "1_2", "status": "undone"},
        {"task_id": "2_1", "status": "done"},
    ]
    runner.completed_tasks = {"2_1"}

    task = {
        "task_id": "1_1",
        "description": "prepare datasets",
        "dependencies": ["2_1"],
        "output": {"format": "JSON", "description": "artifact"},
        "validation": {"criteria": ["non-empty"]},
    }

    await runner._record_task_attempt_failure(
        task_id="1_1",
        phase="execution",
        attempt=1,
        error="Agent reached max turns",
        will_retry=True,
    )

    context = runner._build_task_execution_context(task, {"dep": {"k": "v"}})

    assert context["globalGoal"] == "global objective"
    assert context["planContext"]["currentTaskId"] == "1_1"
    assert context["taskContract"]["outputFormat"] == "JSON"
    assert context["retryMemory"]["attempt"] == 1
    assert "max turns" in context["retryMemory"]["lastFailure"]


def test_build_task_execution_context_includes_retry_memory():
    anyio.run(_run_build_context_with_retry_memory)


async def _run_load_task_attempt_memories():
    async def fake_list(research_id, task_id=None):
        assert research_id == "research_x"
        assert task_id is None
        return [
            {
                "researchId": "research_x",
                "taskId": "1_1",
                "attempt": 1,
                "data": {
                    "attempt": 1,
                    "phase": "execution",
                    "error": "Agent reached max turns",
                    "willRetry": True,
                    "ts": 1000,
                },
                "updatedAt": 1000,
            }
        ]

    deps = RunnerDeps(list_task_attempt_memories=fake_list)
    runner = ExecutionRunner(sio=None, session_id="test", deps=deps)
    runner.research_id = "research_x"

    await runner._load_task_attempt_memories()
    history = runner.task_attempt_history.get("1_1") or []
    assert len(history) == 1
    assert history[0]["attempt"] == 1
    assert "max turns" in history[0]["error"]


def test_load_task_attempt_memories():
    anyio.run(_run_load_task_attempt_memories)


async def _run_retry_task_clears_downstream_history():
    released: list[str] = []
    deleted_artifacts: list[str] = []
    deleted_memories: list[str] = []
    scheduled: list[str] = []

    async def fake_delete_task_artifact(_idea_id, _plan_id, task_id):
        deleted_artifacts.append(task_id)
        return True

    async def fake_delete_task_attempt_memories(_research_id, task_id=None):
        if task_id:
            deleted_memories.append(task_id)
        return 1

    deps = RunnerDeps(
        release_worker=lambda task_id: released.append(task_id),
        delete_task_artifact=fake_delete_task_artifact,
        delete_task_attempt_memories=fake_delete_task_attempt_memories,
    )
    runner = ExecutionRunner(sio=None, session_id="test", deps=deps)
    runner.idea_id = "idea_x"
    runner.plan_id = "plan_y"
    runner.research_id = "research_z"
    runner.is_running = True
    runner.task_map = {
        "1_1": {"task_id": "1_1", "dependencies": [], "status": "done"},
        "1_2_1": {"task_id": "1_2_1", "dependencies": ["1_1"], "status": "validating"},
        "1_2_2": {"task_id": "1_2_2", "dependencies": ["1_2_1"], "status": "pending"},
        "1_2_3": {"task_id": "1_2_3", "dependencies": ["1_2_2"], "status": "done"},
    }
    runner.reverse_dependency_index = {
        "1_1": ["1_2_1"],
        "1_2_1": ["1_2_2"],
        "1_2_2": ["1_2_3"],
        "1_2_3": [],
    }
    runner.running_tasks = {"1_2_1"}
    runner.pending_tasks = {"1_2_2"}
    runner.completed_tasks = {"1_1", "1_2_3"}
    runner.task_attempt_history = {
        "1_2_1": [{"attempt": 1, "category": "runtime", "error": "timeout"}],
        "1_2_2": [{"attempt": 1, "category": "format", "error": "invalid json"}],
        "1_2_3": [{"attempt": 1, "category": "semantic", "error": "metric failed"}],
    }

    def fake_schedule_ready_tasks(tasks):
        for t in tasks or []:
            if t and t.get("task_id"):
                scheduled.append(t["task_id"])

    runner._schedule_ready_tasks = fake_schedule_ready_tasks  # type: ignore[method-assign]

    ok = await runner.retry_task("1_2_1")
    assert ok is True

    for tid in ("1_2_1", "1_2_2", "1_2_3"):
        assert runner.task_map[tid]["status"] == "undone"
        assert tid in runner.pending_tasks
        assert tid not in runner.running_tasks
        assert tid not in runner.completed_tasks
        assert tid not in runner.task_attempt_history

    assert set(released) >= {"1_2_1", "1_2_2", "1_2_3"}
    assert set(deleted_artifacts) == {"1_2_1", "1_2_2", "1_2_3"}
    assert set(deleted_memories) == {"1_2_1", "1_2_2", "1_2_3"}
    assert "1_2_1" in scheduled


def test_retry_task_clears_downstream_history():
    anyio.run(_run_retry_task_clears_downstream_history)


async def _run_unified_retry_counter_increments_consistently():
    deps = RunnerDeps()
    runner = ExecutionRunner(sio=None, session_id="test", deps=deps)

    attempt_1 = runner._next_retry_attempt("3_1")
    attempt_2 = runner._next_retry_attempt("3_1")
    attempt_3 = runner._next_retry_attempt("3_1")

    # Unified retry counter must keep increasing regardless of failure category.
    assert attempt_1 == 1
    assert attempt_2 == 2
    assert attempt_3 == 3


def test_unified_retry_counter_increments_consistently():
    anyio.run(_run_unified_retry_counter_increments_consistently)


async def _run_schedule_ready_tasks_deduplicates_inflight_task():
    deps = RunnerDeps()
    runner = ExecutionRunner(sio=None, session_id="test", deps=deps)
    runner.is_running = True
    task = {"task_id": "3_1", "dependencies": []}
    runner.pending_tasks = {"3_1"}

    calls = {"count": 0}

    async def fake_execute_task(_task):
        calls["count"] += 1
        await anyio.sleep(0.05)

    async def fake_handle_task_error(_task, _error):
        raise AssertionError("_handle_task_error should not be called in this test")

    runner._execute_task = fake_execute_task  # type: ignore[method-assign]
    runner._handle_task_error = fake_handle_task_error  # type: ignore[method-assign]

    # Schedule the same ready task repeatedly while it's still running.
    runner._schedule_ready_tasks([task])
    runner._schedule_ready_tasks([task])
    runner._schedule_ready_tasks([task])

    await anyio.sleep(0.1)

    assert calls["count"] == 1


def test_schedule_ready_tasks_deduplicates_inflight_task():
    anyio.run(_run_schedule_ready_tasks_deduplicates_inflight_task)


async def _run_unified_retry_counter_uses_history_when_memory_resets():
    deps = RunnerDeps()
    runner = ExecutionRunner(sio=None, session_id="test", deps=deps)
    runner.task_attempt_history = {
        "3_1": [
            {"phase": "retry", "attempt": 1, "error": "fail-1"},
            {"phase": "retry", "attempt": 2, "error": "fail-2"},
        ]
    }

    attempt = runner._next_retry_attempt("3_1")

    assert attempt == 3


def test_unified_retry_counter_uses_history_when_memory_resets():
    anyio.run(_run_unified_retry_counter_uses_history_when_memory_resets)


async def _run_retry_sets_forced_next_attempt():
    deps = RunnerDeps(release_worker=lambda _task_id: None)
    runner = ExecutionRunner(sio=None, session_id="test", deps=deps)

    emitted = []
    appended = []

    def fake_emit(event, data):
        emitted.append((event, data))

    async def fake_append(task_id, event, payload):
        appended.append((task_id, event, payload))

    runner._emit = fake_emit
    runner._append_step_event = fake_append  # type: ignore[method-assign]
    runner._spawn_task_execution = lambda _task: None  # type: ignore[method-assign]

    task = {"task_id": "1_2_1", "dependencies": ["1_1"], "status": "validation-failed"}
    await runner._retry_or_fail(
        task=task,
        phase="validation",
        error="validation failed",
        decision={"action": "retry"},
    )

    retry_payloads = [d for e, d in emitted if e in ("attempt-retry", "task-retry")]
    assert retry_payloads, "Expected attempt-retry event"
    retry_payload = retry_payloads[0]
    assert retry_payload.get("attempt") == 1
    assert retry_payload.get("nextAttempt") == 2
    assert runner.task_forced_attempt.get("1_2_1") == 2
    assert any(ev == "attempt-retry" for _, ev, _ in appended)


def test_retry_sets_forced_next_attempt():
    anyio.run(_run_retry_sets_forced_next_attempt)


async def _run_execute_task_uses_forced_attempt_for_all_events():
    async def fake_resolve_artifacts(*_args, **_kwargs):
        return {"raw": "value"}

    async def fake_execute_task(*_args, **kwargs):
        on_thinking = kwargs.get("on_thinking")
        if on_thinking:
            await on_thinking(
                "Calling RunCommand({\"command\": \"echo ok\"})",
                task_id="1_2_1",
                operation="Execute",
                schedule_info={"turn": 1, "max_turns": 200},
            )
        return {"content": "ok"}

    async def fake_save_task_artifact(*_args, **_kwargs):
        return None

    async def fake_save_validation_report(*_args, **_kwargs):
        return None

    async def fake_delete_task_attempt_memories(*_args, **_kwargs):
        return None

    async def fake_stop_execution_container(*_args, **_kwargs):
        return None

    async def fake_reflect(*_args, **_kwargs):
        return None

    deps = RunnerDeps(
        resolve_artifacts=fake_resolve_artifacts,
        execute_task=fake_execute_task,
        save_task_artifact=fake_save_task_artifact,
        save_validation_report=fake_save_validation_report,
        delete_task_attempt_memories=fake_delete_task_attempt_memories,
        stop_execution_container=fake_stop_execution_container,
        assign_task=lambda _task_id: "slot-1",
        release_worker=lambda _task_id: None,
        set_worker_status=lambda _task_id, _status: None,
        chunk_string=lambda s, n: [s],
        MOCK_VALIDATOR_CHUNK_DELAY=0.0,
    )
    runner = ExecutionRunner(sio=None, session_id="test", deps=deps)
    runner.api_config = {"taskUseMock": True}
    runner.VALIDATION_PASS_PROBABILITY = 1.0
    runner.is_running = True
    runner.idea_id = "idea_x"
    runner.plan_id = "plan_y"
    runner.execution_run_id = "exec_test"

    task = {
        "task_id": "1_2_1",
        "description": "clean dataset",
        "dependencies": ["1_1"],
        "input": {"raw": "artifact"},
        "output": {"format": "JSON", "description": "output", "artifact": "x"},
        "validation": {"criteria": ["ok"]},
        "status": "undone",
    }

    runner.task_map = {"1_2_1": task, "1_1": {"task_id": "1_1", "status": "done", "dependencies": []}}
    runner.chain_cache = [
        {"task_id": "1_1", "status": "done", "dependencies": []},
        task,
    ]
    runner.reverse_dependency_index = {"1_1": ["1_2_1"], "1_2_1": []}
    runner.pending_tasks = {"1_2_1"}
    runner.completed_tasks = {"1_1"}
    runner.running_tasks = set()
    runner.task_forced_attempt["1_2_1"] = 2

    emitted = []
    appended = []

    def fake_emit(event, data):
        emitted.append((event, data))

    async def fake_append(task_id, event, payload):
        appended.append((task_id, event, payload))

    runner._emit = fake_emit
    runner._append_step_event = fake_append  # type: ignore[method-assign]
    runner._reflect_on_task = fake_reflect  # type: ignore[method-assign]

    await runner._execute_task(task)

    started = [d for e, d in emitted if e == "task-started"]
    outputs = [d for e, d in emitted if e == "task-output"]
    completed = [d for e, d in emitted if e == "task-completed"]
    assert started and outputs and completed
    assert started[0].get("attempt") == 2
    assert outputs[0].get("attempt") == 2
    assert completed[0].get("attempt") == 2

    thinking_events = [payload for _tid, ev, payload in appended if ev == "task-thinking"]
    assert thinking_events and int(thinking_events[0].get("attempt") or 0) == 2

    # Success path should clear forced state for this task.
    assert "1_2_1" not in runner.task_forced_attempt


def test_execute_task_uses_forced_attempt_for_all_events():
    anyio.run(_run_execute_task_uses_forced_attempt_for_all_events)
