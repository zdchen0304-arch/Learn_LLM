import pytest
import anyio

from plan_agent.llm import executor as plan_exec
from plan_agent import index as plan_index


def test_parse_json_response_from_codeblock():
    out = plan_exec._parse_json_response("```json\n{\"a\": 1}\n```")
    assert out == {"a": 1}


def test_validate_atomicity_response():
    assert plan_exec._validate_atomicity_response({"atomic": True}) is True
    assert plan_exec._validate_atomicity_response({"atomic": 1}) is True
    assert plan_exec._validate_atomicity_response({}) is False


def test_validate_decompose_response_happy_path():
    parent_id = "1"
    result = {
        "tasks": [
            {"task_id": "1_1", "description": "Child 1", "dependencies": []},
            {"task_id": "1_2", "description": "Child 2", "dependencies": ["1_1"]},
        ]
    }
    ok, err = plan_exec._validate_decompose_response(result, parent_id)
    assert ok is True
    assert err == ""


def test_validate_decompose_response_rejects_bad_dependency_order():
    parent_id = "1"
    result = {
        "tasks": [
            {"task_id": "1_1", "description": "Child 1", "dependencies": ["1_2"]},
            {"task_id": "1_2", "description": "Child 2", "dependencies": []},
        ]
    }
    ok, err = plan_exec._validate_decompose_response(result, parent_id)
    assert ok is False
    assert "must be an earlier sibling" in err


def test_build_user_message_atomicity_includes_context():
    msg = plan_exec._build_user_message(
        "atomicity",
        {"task_id": "1", "description": "Test"},
        {"depth": 1, "ancestor_path": "0>1", "idea": "Idea", "siblings": []},
    )
    assert "ancestor path" in msg
    assert "Context - idea" in msg


def test_parse_json_response_invalid_raises():
    out = plan_exec._parse_json_response("not json")
    assert not isinstance(out, dict)


async def _run_agent_plan_repair(monkeypatch):
    async def fake_run_plan_agent(plan, on_thinking, abort_event, on_tasks_batch, api_config, idea_id=None, plan_id=None):
        return {
            "tasks": [
                {"task_id": "0", "title": "Root", "description": "Root task", "dependencies": []},
                {"task_id": "1", "title": "Leaf A", "description": "Prepare data", "dependencies": []},
                {"task_id": "2", "title": "Leaf B", "description": "Train model", "dependencies": ["1"]},
            ],
            "pending_queue": ["1", "2"],
            "finished": False,
            "turn_count": 30,
        }

    async def fake_check_atomicity(task, *args, **kwargs):
        return {"atomic": task.get("task_id") in ("1", "2")}

    async def fake_format_task(task, *args, **kwargs):
        return {
            "input": {"description": f"input for {task['task_id']}"},
            "output": {"description": f"output for {task['task_id']}"},
        }

    monkeypatch.setattr(plan_index, "run_plan_agent", fake_run_plan_agent)
    monkeypatch.setattr(plan_index, "check_atomicity", fake_check_atomicity)
    monkeypatch.setattr(plan_index, "format_task", fake_format_task)

    result = await plan_index.run_plan(
        {"tasks": [{"task_id": "0", "title": "Root", "description": "Root task", "dependencies": []}], "idea": "Root task"},
        on_task=None,
        on_thinking=lambda *args, **kwargs: None,
        abort_event=None,
        on_tasks_batch=None,
        use_mock=False,
        api_config={"planAgentMode": True},
        skip_quality_assessment=True,
        idea_id="idea_test",
        plan_id="plan_test",
    )

    tasks = result.get("tasks") or []
    leaf_1 = next(t for t in tasks if t.get("task_id") == "1")
    leaf_2 = next(t for t in tasks if t.get("task_id") == "2")
    assert leaf_1.get("input") and leaf_1.get("output")
    assert leaf_2.get("input") and leaf_2.get("output")


def test_agent_mode_plan_is_repaired_to_atomic_tasks(monkeypatch):
    anyio.run(_run_agent_plan_repair, monkeypatch)
