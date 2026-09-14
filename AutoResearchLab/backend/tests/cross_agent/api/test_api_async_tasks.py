from async_runtime.broker import InMemoryTaskBroker
from async_runtime.context import InMemoryContextStore
from async_runtime.runtime import AsyncResearchRuntime


def test_async_task_api_dispatches_compact_command(client, session_headers, monkeypatch):
    from api.routes import async_tasks

    runtime = AsyncResearchRuntime(context_store=InMemoryContextStore(), broker=InMemoryTaskBroker())
    monkeypatch.setattr(async_tasks, "_runtime", runtime)
    created = client.post("/api/research", json={"prompt": "Test async research"}, headers=session_headers)
    research_id = created.json()["researchId"]

    dispatched = client.post(
        f"/api/research/{research_id}/async-tasks",
        json={
            "stage": "execute",
            "artifactRefs": ["artifact:plan:v1"],
            "idempotencyKey": "api-async-task-key",
        },
        headers=session_headers,
    )
    assert dispatched.status_code == 202
    task = dispatched.json()["task"]
    assert task["stage"] == "execute"
    assert task["contextRef"].startswith(f"research:{research_id}:run:")

    listed = client.get(f"/api/research/{research_id}/async-tasks", headers=session_headers)
    assert listed.status_code == 200
    assert listed.json()["items"][0]["taskId"] == task["taskId"]

    duplicate = client.post(
        f"/api/research/{research_id}/async-tasks",
        json={"stage": "execute", "idempotencyKey": "api-async-task-key"},
        headers=session_headers,
    )
    assert duplicate.status_code == 409


def test_async_runtime_status_is_explicit_when_not_configured(client, session_headers, monkeypatch):
    from api.routes import async_tasks

    monkeypatch.setattr(async_tasks, "_runtime", None)
    monkeypatch.setenv("MAARS_ASYNC_MODE", "disabled")
    response = client.get("/api/async-runtime/status", headers=session_headers)
    assert response.status_code == 200
    assert response.json()["ready"] is False


def test_research_run_endpoint_accepts_async_mode_and_queues_refine(client, session_headers, monkeypatch):
    from api.routes import async_tasks

    runtime = AsyncResearchRuntime(context_store=InMemoryContextStore(), broker=InMemoryTaskBroker())
    monkeypatch.setattr(async_tasks, "_runtime", runtime)
    created = client.post("/api/research", json={"prompt": "Queue this research"}, headers=session_headers)
    research_id = created.json()["researchId"]

    response = client.post(
        f"/api/research/{research_id}/run",
        json={"executionMode": "async"},
        headers=session_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "async-queued"
    assert payload["task"]["stage"] == "refine"

    record = client.get(f"/api/research/{research_id}", headers=session_headers).json()["research"]
    assert record["stage"] == "refine"
    assert record["stageStatus"] == "queued"
