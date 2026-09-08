"""
Literature provider routing for Idea Agent.
"""

from typing import Optional

from . import arxiv, openalex

DEFAULT_LITERATURE_SOURCE = "openalex"
_SUPPORTED_SOURCES = {"openalex", "arxiv"}


def normalize_literature_source(source: Optional[str]) -> str:
    s = str(source or "").strip().lower()
    if s not in _SUPPORTED_SOURCES:
        return DEFAULT_LITERATURE_SOURCE
    return s


async def search_literature(query: str, *, limit: int, cat: Optional[str], source: Optional[str]) -> tuple[str, list[dict]]:
    provider = normalize_literature_source(source)
    if provider == "arxiv":
        return provider, await arxiv.search_arxiv(query, limit=limit, cat=cat)
    return provider, await openalex.search_openalex(query, limit=limit)
