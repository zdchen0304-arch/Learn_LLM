import pytest

from task_agent.agent_tools import run_finish
from task_agent.runner import ExecutionRunner
from task_agent.llm import executor as task_exec
from task_agent.llm.validation import (
    classify_validation_failure,
)
from plan_agent.llm import executor as plan_exec


def test_run_finish_rejects_prose_for_structured_output():
    ok, value = run_finish("filtered signal saved to sandbox/out.csv", output_format="Numerical Array or Time-series Object")
    assert ok is False
    assert "must be valid JSON" in value


def test_classify_validation_failure_detects_format_and_evidence():
    format_case = classify_validation_failure("Output format: FAIL (Expected numerical array/time-series, received text description)")
    evidence_case = classify_validation_failure("Signal length match: FAIL (Data not provided)")
    assert format_case["category"] == "format"
    assert evidence_case["category"] == "evidence_missing"

@pytest.mark.asyncio
async def test_runner_step_b_contract_review_applies_adjustment(monkeypatch):
    runner = ExecutionRunner(sio=None)
    runner.api_config = {"taskUseMock": False}
    runner.abort_event = None
    runner.docker_runtime_status = {"available": True}
    runner.task_attempt_history = {
        "1_2_3": [
            {"category": "format", "decision": "regenerate_output", "summary": "bad structure"},
            {"category": "semantic", "decision": "redo_step", "summary": "metric shortfall"},
        ]
    }

    async def fake_review_contract_adjustment(packet, **kwargs):
        return {
            "shouldAdjust": True,
            "immutableImpacted": False,
            "reasoning": "Return artifact-based criteria to avoid impossible in-memory checks.",
            "proposedValidationCriteria": [
                "Deliver output as loadable artifact path with schema metadata.",
            ],
            "patchSummary": "Switch to artifact-based validation for this step.",
            "source": "step-b-agent",
        }

    monkeypatch.setattr("task_agent.runner.review_contract_adjustment", fake_review_contract_adjustment)

    task = {
        "task_id": "1_2_3",
        "description": "Prepare filtered ECG dataset",
        "dependencies": ["1_2_1"],
        "output": {"format": "Numerical Array or Time-series Object", "artifact": "filtered_ecg", "description": "Prepared ECG array"},
        "validation": {"criteria": ["Provide loadable array output"]},
    }

    decision = await runner._run_step_b_contract_review(
        task={
            **task,
        },
        result={"filtered_ecg_path": "sandbox/ecg_prepared.npz"},
        reason="Output format: FAIL (Expected numerical array/time-series, received file path)",
        output_format="Numerical Array or Time-series Object",
        on_thinking=None,
    )

    assert decision["source"] == "step-b-agent"
    assert decision["shouldAdjust"] is True
    assert decision["immutableImpacted"] is False
    assert task["validation"]["criteria"] == [
        "Deliver output as loadable artifact path with schema metadata.",
    ]


@pytest.mark.asyncio
async def test_execute_task_repairs_structured_output(monkeypatch):
    responses = iter([
        "The filtered signal is saved to sandbox/filtered.csv.",
        "```json\n{\"filtered_ecg_path\": \"sandbox/filtered.csv\", \"shape\": [500, 12], \"status\": \"success\"}\n```",
    ])

    async def fake_chat_completion(*args, **kwargs):
        return next(responses)

    monkeypatch.setattr(task_exec, "chat_completion", fake_chat_completion)

    result = await task_exec.execute_task(
        task_id="1_2_2",
        description="Filter ECG",
        input_spec={"description": "", "artifacts": [], "parameters": []},
        output_spec={"description": "Filtered ECG output", "artifact": "filtered_ecg", "format": "Numerical Array or Time-series Object"},
        resolved_inputs={},
        api_config={},
        abort_event=None,
        on_thinking=None,
    )

    assert isinstance(result, dict)
    assert result["filtered_ecg_path"] == "sandbox/filtered.csv"


@pytest.mark.asyncio
async def test_plan_format_task_repairs_invalid_output(monkeypatch):
    responses = iter([
        "not json",
        "```json\n{\"input\": {\"description\": \"input\"}, \"output\": {\"description\": \"output\"}}\n```",
    ])

    async def fake_real_chat_completion(*args, **kwargs):
        return next(responses)

    monkeypatch.setattr(plan_exec, "real_chat_completion", fake_real_chat_completion)

    result = await plan_exec.format_task(
        {"task_id": "1", "description": "Prepare data", "dependencies": []},
        on_thinking=lambda *args, **kwargs: None,
        abort_event=None,
        use_mock=False,
        api_config={},
    )

    assert isinstance(result, dict)
    assert result["input"]["description"] == "input"
    assert result["output"]["description"] == "output"