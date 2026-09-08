"""
OpenAlex API 请求与解析。
"""

import time
from typing import List

import httpx
from loguru import logger

OPENALEX_API_BASE = "https://api.openalex.org/works"


def _decode_inverted_index(index: dict | None) -> str:
    if not isinstance(index, dict) or not index:
        return ""
    positions: list[tuple[int, str]] = []
    for token, pos_list in index.items():
        if not isinstance(token, str) or not isinstance(pos_list, list):
            continue
        for pos in pos_list:
            try:
                p = int(pos)
            except Exception:
                continue
            positions.append((p, token))
    if not positions:
        return ""
    positions.sort(key=lambda x: x[0])
    return " ".join(token for _, token in positions).strip()


def _parse_work(work: dict) -> dict | None:
    if not isinstance(work, dict):
        return None

    title = str(work.get("title") or "").strip()
    if not title:
        return None

    abstract = _decode_inverted_index(work.get("abstract_inverted_index"))

    primary_location = work.get("primary_location") or {}
    landing_page = ""
    if isinstance(primary_location, dict):
        landing_page = str(primary_location.get("landing_page_url") or "").strip()
    doi = str(work.get("doi") or "").strip()
    work_id = str(work.get("id") or "").strip()
    url = landing_page or doi or work_id

    authors = []
    for authorship in (work.get("authorships") or []):
        if not isinstance(authorship, dict):
            continue
        author_obj = authorship.get("author") or {}
        if not isinstance(author_obj, dict):
            continue
        name = str(author_obj.get("display_name") or "").strip()
        if name:
            authors.append(name)

    published = str(work.get("publication_date") or "").strip()[:10]

    return {
        "title": title,
        "abstract": abstract,
        "url": url,
        "authors": authors,
        "published": published,
    }


async def search_openalex(query: str, limit: int = 10) -> List[dict]:
    """
    检索 OpenAlex works，返回统一文献结构。

    Returns:
        [{title, abstract, url, authors, published}, ...]
    """
    if not query or not isinstance(query, str):
        return []
    cleaned_query = query.replace("+", " ").strip()
    if not cleaned_query:
        return []

    limit = min(max(1, int(limit) if isinstance(limit, (int, float)) else 10), 50)
    params = {
        "search": cleaned_query,
        "per-page": str(limit),
        "sort": "relevance_score:desc",
    }
    started = time.perf_counter()
    logger.info("OpenAlex search start query='{}' limit={}", cleaned_query, limit)

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(OPENALEX_API_BASE, params=params)
            resp.raise_for_status()
            data = resp.json() if resp.content else {}
            logger.info(
                "OpenAlex search response query='{}' status={} bytes={} elapsed_ms={}",
                cleaned_query,
                resp.status_code,
                len(resp.content or b""),
                int((time.perf_counter() - started) * 1000),
            )
    except httpx.HTTPStatusError as e:
        logger.warning("OpenAlex API HTTP error for query '{}': {}", cleaned_query, e)
        raise RuntimeError(f"OpenAlex HTTP error for query '{cleaned_query}': {e}") from e
    except httpx.RequestError as e:
        logger.warning("OpenAlex API request error for query '{}': {}", cleaned_query, e)
        raise RuntimeError(f"OpenAlex request error for query '{cleaned_query}': {e}") from e

    works = data.get("results") if isinstance(data, dict) else []
    results = []
    for work in (works or []):
        parsed = _parse_work(work)
        if parsed:
            results.append(parsed)

    logger.info(
        "OpenAlex search complete query='{}' papers={} elapsed_ms={}",
        cleaned_query,
        len(results),
        int((time.perf_counter() - started) * 1000),
    )
    return results
