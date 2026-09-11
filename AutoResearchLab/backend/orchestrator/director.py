"""Research Director control-plane snapshot builder.

The existing pipeline remains responsible for running stages.  This module
makes its delegation contracts and quality gates explicit, so a UI can show
the difference between the agent organisation, task DAG, and evidence graph.
"""

from __future__ import annotations

from typing import Any


STAGE_DEFINITIONS = (
    {
        "stage": "refine",
        "lead": "Literature Lead",
        "workers": ["Literature Scout", "Evidence Curator"],
        "goal": "Convert a broad topic into an evidence-grounded research question.",
        "expectedOutputs": ["keywords", "papers", "refined_idea"],
        "dependsOn": [],
    },
    {
        "stage": "plan",
        "lead": "Planning Lead",
        "workers": ["Task Decomposer", "Method Designer"],
        "goal": "Create an atomic, dependency-aware research plan.",
        "expectedOutputs": ["task_dag", "acceptance_criteria"],
        "dependsOn": ["refine"],
    },
    {
        "stage": "execute",
        "lead": "Execution Lead",
        "workers": ["Experiment Worker", "Validation Worker"],
        "goal": "Produce and validate the planned research artifacts.",
        "expectedOutputs": ["task_outputs", "validation_reports"],
        "dependsOn": ["plan"],
    },
    {
        "stage": "paper",
        "lead": "Writing Lead",
        "workers": ["Section Writer", "Paper Quality Reviewer"],
        "goal": "Synthesize validated artifacts into a traceable paper draft.",
        "expectedOutputs": ["paper_draft", "paper_quality_review"],
        "dependsOn": ["execute"],
    },
)


def _has_refine_artifacts(idea: dict | None) -> bool:
    return bool(idea and idea.get("refined_idea") and idea.get("keywords"))


def _has_plan_artifacts(plan: dict | None) -> bool:
    return bool(plan and plan.get("tasks"))


def _has_execution_artifacts(execution: dict | None, outputs: dict | None) -> bool:
    """Match the executable task set, not every node in the decomposition tree."""
    tasks = (execution or {}).get("tasks") or []
    if not tasks:
        return False
    output_ids = set((outputs or {}).keys())
    task_ids = {str(task.get("task_id") or task.get("id") or "") for task in tasks}
    task_ids.discard("")
    return bool(task_ids) and task_ids.issubset(output_ids)


def _has_paper_artifact(paper: dict | None) -> bool:
    return bool(paper and str(paper.get("content") or "").strip())


def _review_blocking_count(paper_review: dict | None) -> int:
    report = (paper_review or {}).get("report") if isinstance(paper_review, dict) else {}
    try:
        return int((report or {}).get("blockingIssueCount") or 0)
    except (TypeError, ValueError):
        return 0


class ResearchDirector:
    """Build a read-only, inspectable control-plane view for one research run."""

    def snapshot(
        self,
        *,
        research: dict,
        idea: dict | None,
        plan: dict | None,
        execution: dict | None,
        outputs: dict | None,
        paper: dict | None,
        paper_review: dict | None = None,
    ) -> dict[str, Any]:
        stage_status = str(research.get("stageStatus") or "idle").lower()
        active_stage = str(research.get("stage") or "refine").lower()

        gates = self._gates(
            active_stage=active_stage,
            stage_status=stage_status,
            idea=idea,
            plan=plan,
            execution=execution,
            outputs=outputs,
            paper=paper,
            paper_review=paper_review,
        )
        contracts = self._stage_contracts(gates, plan, execution)
        director_decision = self._decision(active_stage, stage_status, gates)

        return {
            "researchId": research.get("researchId"),
            "director": {
                "name": "Research Director",
                "role": "control-plane supervisor",
                "activeStage": active_stage,
                "stageStatus": stage_status,
                "decision": director_decision,
            },
            "agentOrganization": self._organization(),
            "qualityGates": gates,
            "taskContracts": contracts,
            "evidenceTrail": self._evidence_trail(idea, plan, outputs, paper, paper_review),
            "artifactSummary": {
                "literatureCount": len((idea or {}).get("papers") or []),
                "planTaskCount": len((plan or {}).get("tasks") or []),
                "executionOutputCount": len(outputs or {}),
                "hasPaperDraft": _has_paper_artifact(paper),
                "hasPaperQualityReview": bool(paper_review),
                "paperReviewBlockingIssueCount": _review_blocking_count(paper_review),
            },
        }

    def _gates(
        self,
        *,
        active_stage: str,
        stage_status: str,
        idea: dict | None,
        plan: dict | None,
        execution: dict | None,
        outputs: dict | None,
        paper: dict | None,
        paper_review: dict | None,
    ) -> list[dict[str, Any]]:
        checks = {
            "refine": _has_refine_artifacts(idea),
            "plan": _has_plan_artifacts(plan),
            "execute": _has_execution_artifacts(execution, outputs),
            "paper": _has_paper_artifact(paper) and bool(paper_review) and _review_blocking_count(paper_review) == 0,
        }
        result: list[dict[str, Any]] = []
        previous_passed = True
        for definition in STAGE_DEFINITIONS:
            stage = definition["stage"]
            passed = checks[stage]
            if stage == "paper" and _has_paper_artifact(paper) and paper_review and _review_blocking_count(paper_review) > 0:
                status = "needs_revision"
            elif stage == active_stage and stage_status == "failed":
                status = "failed"
            elif passed:
                status = "passed"
            elif not previous_passed:
                status = "blocked"
            elif stage == active_stage and stage_status == "running":
                status = "running"
            else:
                status = "pending"
            result.append(
                {
                    "gateId": f"gate:{stage}",
                    "stage": stage,
                    "status": status,
                    "criteria": definition["expectedOutputs"],
                    "reason": self._gate_reason(stage, status),
                }
            )
            previous_passed = previous_passed and passed
        return result

    @staticmethod
    def _gate_reason(stage: str, status: str) -> str:
        if status == "passed":
            return "Required artifacts are available for the next delegation."
        if status == "running":
            return "The Director is waiting for the current delegation to satisfy its contract."
        if status == "failed":
            return "The current stage failed validation and requires retry or re-planning."
        if status == "needs_revision":
            return "The paper review found blocking issues; revise claims or supporting evidence."
        if status == "blocked":
            return "An upstream quality gate has not passed."
        if stage == "paper":
            return "A paper draft and a paper-quality review are required before completion."
        return "Awaiting its upstream contract and required artifacts."

    @staticmethod
    def _organization() -> list[dict[str, Any]]:
        result = [{"id": "director", "name": "Research Director", "reportsTo": None, "kind": "supervisor"}]
        for definition in STAGE_DEFINITIONS:
            lead_id = f"lead:{definition['stage']}"
            result.append({"id": lead_id, "name": definition["lead"], "reportsTo": "director", "kind": "lead"})
            result.extend(
                {
                    "id": f"worker:{definition['stage']}:{index}",
                    "name": worker,
                    "reportsTo": lead_id,
                    "kind": "worker",
                }
                for index, worker in enumerate(definition["workers"])
            )
        return result

    @staticmethod
    def _stage_contracts(gates: list[dict], plan: dict | None, execution: dict | None) -> list[dict[str, Any]]:
        gate_status = {gate["stage"]: gate["status"] for gate in gates}
        contracts = []
        for definition in STAGE_DEFINITIONS:
            stage = definition["stage"]
            contracts.append(
                {
                    "contractId": f"stage:{stage}",
                    "owner": definition["lead"],
                    "goal": definition["goal"],
                    "dependsOn": [f"stage:{dependency}" for dependency in definition["dependsOn"]],
                    "expectedOutputs": definition["expectedOutputs"],
                    "status": gate_status[stage],
                }
            )

        task_statuses = {
            str(task.get("task_id") or task.get("id") or ""): str(task.get("status") or "pending")
            for task in ((execution or {}).get("tasks") or [])
        }
        for task in (plan or {}).get("tasks") or []:
            task_id = str(task.get("task_id") or task.get("id") or "").strip()
            if not task_id:
                continue
            output_spec = task.get("output_spec") or task.get("output") or {}
            if isinstance(output_spec, dict):
                expected_output = output_spec.get("format") or output_spec.get("artifact") or "validated task output"
            else:
                expected_output = str(output_spec) or "validated task output"
            contracts.append(
                {
                    "contractId": f"task:{task_id}",
                    "owner": "Experiment Worker",
                    "goal": task.get("description") or "Execute planned research task.",
                    "dependsOn": [f"task:{item}" for item in (task.get("dependencies") or [])],
                    "expectedOutputs": [expected_output],
                    "status": task_statuses.get(task_id, "pending"),
                }
            )
        return contracts

    @staticmethod
    def _evidence_trail(
        idea: dict | None,
        plan: dict | None,
        outputs: dict | None,
        paper: dict | None,
        paper_review: dict | None,
    ) -> list[dict[str, Any]]:
        """Expose artifact provenance without pretending it is the task DAG."""
        trail: list[dict[str, Any]] = []
        for index, item in enumerate((idea or {}).get("papers") or []):
            title = item.get("title") if isinstance(item, dict) else str(item)
            trail.append(
                {
                    "artifactId": f"literature:{index}",
                    "kind": "literature",
                    "label": title or f"Literature item {index + 1}",
                    "producedBy": "Literature Scout",
                    "dependsOn": [],
                }
            )
        for task in (plan or {}).get("tasks") or []:
            task_id = str(task.get("task_id") or task.get("id") or "").strip()
            if not task_id:
                continue
            trail.append(
                {
                    "artifactId": f"plan:{task_id}",
                    "kind": "task_specification",
                    "label": task.get("title") or task.get("description") or f"Task {task_id}",
                    "producedBy": "Task Decomposer",
                    "dependsOn": [f"plan:{dependency}" for dependency in (task.get("dependencies") or [])],
                }
            )
        for task_id, output in (outputs or {}).items():
            value = output.get("content") if isinstance(output, dict) else output
            label = str(value or "").strip().replace("\n", " ")[:90] or f"Output for task {task_id}"
            trail.append(
                {
                    "artifactId": f"output:{task_id}",
                    "kind": "validated_output",
                    "label": label,
                    "producedBy": "Experiment Worker",
                    "dependsOn": [f"plan:{task_id}"],
                }
            )
        if _has_paper_artifact(paper):
            trail.append(
                {
                    "artifactId": "paper:draft",
                    "kind": "paper_draft",
                    "label": "Paper draft",
                    "producedBy": "Section Writer",
                    "dependsOn": [f"output:{task_id}" for task_id in (outputs or {}).keys()],
                }
            )
        if paper_review:
            trail.append(
                {
                    "artifactId": "paper:review",
                    "kind": "quality_review",
                    "label": "Paper quality review",
                    "producedBy": "Paper Quality Reviewer",
                    "dependsOn": ["paper:draft"],
                }
            )
        return trail

    @staticmethod
    def _decision(active_stage: str, stage_status: str, gates: list[dict]) -> str:
        current = next((gate for gate in gates if gate["stage"] == active_stage), None)
        if current and current["status"] == "failed":
            return f"Re-plan or retry {active_stage}: its quality gate failed."
        revision_gate = next((gate for gate in gates if gate["status"] == "needs_revision"), None)
        if revision_gate:
            return f"Revise {revision_gate['stage']} using the blocking findings from its quality review."
        next_gate = next((gate for gate in gates if gate["status"] in {"pending", "blocked"}), None)
        if next_gate:
            return f"Delegate {next_gate['stage']} when its upstream gate is satisfied."
        if stage_status == "running":
            return f"Monitor {active_stage} and wait for contract completion."
        return "All visible contracts are complete; verify final review findings before publishing."
