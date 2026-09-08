import json

import anyio

import idea_agent
from idea_agent import agent_tools


async def _run_collect_uses_openalex_by_default(monkeypatch):
    async def fake_extract_keywords(*_args, **_kwargs):
        return ["pca", "lda"]

    async def fake_refine(*_args, **_kwargs):
        return "refined"

    async def fake_openalex(query, limit=10):
        assert query
        assert limit == 5
        return [{"title": "OA Paper", "abstract": "a", "url": "u", "authors": [], "published": "2024-01-01"}]

    async def fake_arxiv(*_args, **_kwargs):
        raise AssertionError("arxiv should not be called when default source is openalex")

    monkeypatch.setattr(idea_agent, "extract_keywords", fake_extract_keywords)
    monkeypatch.setattr(idea_agent, "refine_idea_from_papers", fake_refine)
    monkeypatch.setattr("idea_agent.openalex.search_openalex", fake_openalex)
    monkeypatch.setattr("idea_agent.arxiv.search_arxiv", fake_arxiv)

    result = await idea_agent.collect_literature("dimensionality reduction", api_config={}, limit=5)
    assert result["papers"] and result["papers"][0]["title"] == "OA Paper"


async def _run_collect_uses_arxiv_when_selected(monkeypatch):
    async def fake_extract_keywords(*_args, **_kwargs):
        return ["pca"]

    async def fake_refine(*_args, **_kwargs):
        return "refined"

    async def fake_arxiv(query, limit=10, cat=None):
        assert query
        assert limit == 3
        assert cat is None
        return [{"title": "AX Paper", "abstract": "a", "url": "u", "authors": [], "published": "2023-01-01"}]

    async def fake_openalex(*_args, **_kwargs):
        raise AssertionError("openalex should not be called when source=arxiv")

    monkeypatch.setattr(idea_agent, "extract_keywords", fake_extract_keywords)
    monkeypatch.setattr(idea_agent, "refine_idea_from_papers", fake_refine)
    monkeypatch.setattr("idea_agent.arxiv.search_arxiv", fake_arxiv)
    monkeypatch.setattr("idea_agent.openalex.search_openalex", fake_openalex)

    result = await idea_agent.collect_literature(
        "dimensionality reduction",
        api_config={"literatureSource": "arxiv"},
        limit=3,
    )
    assert result["papers"] and result["papers"][0]["title"] == "AX Paper"


async def _run_search_tool_respects_source(monkeypatch):
    async def fake_openalex(query, limit=10):
        assert query
        return [{"title": "OA via tool", "abstract": "a", "url": "u", "authors": [], "published": "2024-02-01"}]

    monkeypatch.setattr("idea_agent.openalex.search_openalex", fake_openalex)

    finished, result_text = await agent_tools.execute_idea_agent_tool(
        "SearchArxiv",
        json.dumps({"keywords": ["principal component analysis"], "limit": 4}),
        idea_state={},
        api_config={"literatureSource": "openalex"},
    )
    assert finished is False
    payload = json.loads(result_text)
    assert payload.get("source") == "openalex"
    assert payload.get("count") == 1


def test_collect_uses_openalex_by_default(monkeypatch):
    anyio.run(_run_collect_uses_openalex_by_default, monkeypatch)


def test_collect_uses_arxiv_when_selected(monkeypatch):
    anyio.run(_run_collect_uses_arxiv_when_selected, monkeypatch)


def test_search_tool_respects_source(monkeypatch):
    anyio.run(_run_search_tool_respects_source, monkeypatch)
