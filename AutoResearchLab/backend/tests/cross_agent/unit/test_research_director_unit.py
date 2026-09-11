from orchestrator import ResearchDirector


def test_director_separates_stage_gates_from_task_contracts():
    snapshot = ResearchDirector().snapshot(
        research={"researchId": "research_1", "stage": "execute", "stageStatus": "running"},
        idea={"keywords": ["agents"], "refined_idea": "Study agent coordination", "papers": [{"title": "P"}]},
        plan={"tasks": [{"task_id": "1", "description": "Run baseline", "dependencies": []}]},
        execution={"tasks": [{"task_id": "1", "status": "running"}]},
        outputs={},
        paper=None,
    )

    assert snapshot["director"]["name"] == "Research Director"
    assert [gate["status"] for gate in snapshot["qualityGates"]] == ["passed", "passed", "running", "blocked"]
    assert any(contract["contractId"] == "task:1" for contract in snapshot["taskContracts"])
    assert len(snapshot["agentOrganization"]) > 4
    assert any(item["artifactId"] == "plan:1" for item in snapshot["evidenceTrail"])


def test_director_requires_revision_when_review_has_blocking_issue():
    snapshot = ResearchDirector().snapshot(
        research={"researchId": "research_2", "stage": "paper", "stageStatus": "completed"},
        idea={"keywords": ["agents"], "refined_idea": "Study agent coordination"},
        plan={"tasks": [{"task_id": "1", "description": "Run baseline", "dependencies": []}]},
        execution={"tasks": [{"task_id": "1", "status": "completed"}]},
        outputs={"1": {"content": "baseline result"}},
        paper={"content": "# Draft"},
        paper_review={"report": {"blockingIssueCount": 1}},
    )

    paper_gate = next(gate for gate in snapshot["qualityGates"] if gate["stage"] == "paper")
    assert paper_gate["status"] == "needs_revision"
    assert "Revise paper" in snapshot["director"]["decision"]
    assert any(item["artifactId"] == "paper:review" for item in snapshot["evidenceTrail"])
