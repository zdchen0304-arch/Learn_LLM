import anyio

from paper_agent.review import review_paper


def test_mock_paper_review_returns_structured_report():
    async def _review():
        return await review_paper(
            content="# Draft\n\nA claim.",
            plan={"tasks": [{"task_id": "1"}]},
            outputs={"1": {"content": "evidence"}},
            api_config={"paperUseMock": True},
        )

    report = anyio.run(_review)

    assert report["summary"]
    assert report["blockingIssueCount"] == 0
    assert set(report["scores"]) >= {"structure", "claimEvidence"}
