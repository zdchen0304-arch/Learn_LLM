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
        "lead": "文献负责人",
        "workers": ["文献检索 Agent", "证据整理 Agent"],
        "goal": "将宽泛主题收敛为有证据支撑的研究问题。",
        "expectedOutputs": ["keywords", "papers", "refined_idea"],
        "dependsOn": [],
    },
    {
        "stage": "plan",
        "lead": "规划负责人",
        "workers": ["任务分解 Agent", "方法设计 Agent"],
        "goal": "生成原子化、具备依赖关系的研究计划。",
        "expectedOutputs": ["task_dag", "acceptance_criteria"],
        "dependsOn": ["refine"],
    },
    {
        "stage": "execute",
        "lead": "执行负责人",
        "workers": ["实验执行 Agent", "结果验证 Agent"],
        "goal": "产出并验证计划中的研究成果。",
        "expectedOutputs": ["task_outputs", "validation_reports"],
        "dependsOn": ["plan"],
    },
    {
        "stage": "paper",
        "lead": "写作负责人",
        "workers": ["章节写作 Agent", "论文质量审查 Agent"],
        "goal": "将验证后的产物整合为可追溯的论文草稿。",
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
                "name": "研究总监",
                "role": "控制面监督者",
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
            return "所需产物已齐备，可以委派下一阶段。"
        if status == "running":
            return "研究总监正在等待当前阶段满足交接契约。"
        if status == "failed":
            return "当前阶段未通过验证，需要重试或重新规划。"
        if status == "needs_revision":
            return "论文审查发现阻塞问题，需要修改论断或补充支撑证据。"
        if status == "blocked":
            return "上游质量门尚未通过。"
        if stage == "paper":
            return "完成前必须具备论文草稿和论文质量审查结果。"
        return "正在等待上游交接条件和所需产物。"

    @staticmethod
    def _organization() -> list[dict[str, Any]]:
        result = [{"id": "director", "name": "研究总监", "reportsTo": None, "kind": "supervisor"}]
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
                    "owner": "实验执行 Agent",
                    "goal": task.get("description") or "执行已规划的研究任务。",
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
                    "producedBy": "文献检索 Agent",
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
                    "producedBy": "任务分解 Agent",
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
                    "producedBy": "实验执行 Agent",
                    "dependsOn": [f"plan:{task_id}"],
                }
            )
        if _has_paper_artifact(paper):
            trail.append(
                {
                    "artifactId": "paper:draft",
                    "kind": "paper_draft",
                    "label": "论文草稿",
                    "producedBy": "章节写作 Agent",
                    "dependsOn": [f"output:{task_id}" for task_id in (outputs or {}).keys()],
                }
            )
        if paper_review:
            trail.append(
                {
                    "artifactId": "paper:review",
                    "kind": "quality_review",
                    "label": "论文质量审查",
                    "producedBy": "论文质量审查 Agent",
                    "dependsOn": ["paper:draft"],
                }
            )
        return trail

    @staticmethod
    def _decision(active_stage: str, stage_status: str, gates: list[dict]) -> str:
        current = next((gate for gate in gates if gate["stage"] == active_stage), None)
        if current and current["status"] == "failed":
            return f"{active_stage} 未通过质量门：请重新规划或重试。"
        revision_gate = next((gate for gate in gates if gate["status"] == "needs_revision"), None)
        if revision_gate:
            return f"请依据论文审查的阻塞问题修改 {revision_gate['stage']} 阶段。"
        next_gate = next((gate for gate in gates if gate["status"] in {"pending", "blocked"}), None)
        if next_gate:
            return f"上游质量门通过后，委派 {next_gate['stage']} 阶段。"
        if stage_status == "running":
            return f"正在监控 {active_stage} 阶段，等待其完成交接契约。"
        return "所有可见交接契约均已完成；发布前请确认最终审查结论。"
