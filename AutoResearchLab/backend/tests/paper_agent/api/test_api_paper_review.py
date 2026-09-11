import anyio

from db import get_paper, get_paper_review, save_paper, save_plan


def test_manual_paper_review_persists_structured_report(client, session_headers, monkeypatch):
    async def _seed() -> None:
        await save_plan(
            {"tasks": [{"task_id": "1", "description": "Produce evidence", "dependencies": []}]},
            "idea_review_api",
            "plan_review_api",
        )
        await save_paper(
            "idea_review_api",
            "plan_review_api",
            format_type="markdown",
            content="# Draft\n\nEvidence-backed claim.",
        )

    async def _fake_review(**_kwargs):
        return {
            "summary": "Review complete.",
            "blockingIssueCount": 1,
            "scores": {"structure": 3},
            "claimAudit": [],
            "findings": [{"id": "PQR-001", "severity": "blocker"}],
            "revisionPlan": [],
        }

    anyio.run(_seed)
    from api.routes import paper as paper_routes

    monkeypatch.setattr(paper_routes, "review_paper", _fake_review)
    response = client.post(
        "/api/paper/review",
        headers=session_headers,
        json={"ideaId": "idea_review_api", "planId": "plan_review_api"},
    )

    assert response.status_code == 200
    assert response.json()["review"]["blockingIssueCount"] == 1
    persisted = anyio.run(get_paper_review, "idea_review_api", "plan_review_api")
    assert persisted and persisted["report"]["findings"][0]["severity"] == "blocker"


def test_paper_run_automatically_persists_review_and_emits_event(monkeypatch):
    idea_id = "idea_auto_review"
    plan_id = "plan_auto_review"

    async def _seed() -> None:
        await save_plan(
            {"tasks": [{"task_id": "1", "description": "Produce evidence", "dependencies": []}]},
            idea_id,
            plan_id,
        )

    async def _fake_config():
        return {"paperUseMock": True}

    async def _fake_run_paper_agent(**_kwargs):
        return "# Generated draft\n\nA supported claim."

    async def _fake_review(**_kwargs):
        return {
            "summary": "Automatic review complete.",
            "blockingIssueCount": 0,
            "scores": {"structure": 4},
            "claimAudit": [],
            "findings": [],
            "revisionPlan": [],
        }

    emitted = []

    async def _fake_emit(*args, **_kwargs):
        emitted.append((args[1], args[2]))

    anyio.run(_seed)
    from api import state as api_state
    from api.state import PaperRunState
    from api.routes import paper as paper_routes

    monkeypatch.setattr(paper_routes, "get_effective_config", _fake_config)
    monkeypatch.setattr(paper_routes, "run_paper_agent", _fake_run_paper_agent)
    monkeypatch.setattr(paper_routes, "review_paper", _fake_review)
    monkeypatch.setattr(api_state, "emit", _fake_emit)
    monkeypatch.setattr(api_state, "emit_safe", _fake_emit)

    anyio.run(
        paper_routes._run_paper_inner,
        "session_auto_review",
        PaperRunState(),
        idea_id,
        plan_id,
        "markdown",
    )

    assert (anyio.run(get_paper, idea_id, plan_id) or {})["content"].startswith("# Generated")
    assert (anyio.run(get_paper_review, idea_id, plan_id) or {})["report"]["blockingIssueCount"] == 0
    assert any(name == "paper-review-complete" for name, _payload in emitted)
