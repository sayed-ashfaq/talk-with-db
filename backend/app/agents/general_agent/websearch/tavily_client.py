"""A thin, synchronous wrapper around Tavily's search API — sync because this is called from inside
websearch_agent_node, which runs on a worker thread already (see app.router.chat). httpx rather than
a Tavily SDK: it's already a dependency, and one POST doesn't need a client library of its own.
"""

from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_URL = "https://api.tavily.com/search"
_TIMEOUT = 10.0
MAX_RESULTS = 5


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    content: str


def search(query: str) -> list[SearchResult]:
    """Empty when Tavily isn't configured or the request fails — the caller treats that the same
    as a real zero-results search, rather than crashing the whole chat turn over an optional tool."""
    if not settings.tavily_api_key:
        return []

    try:
        response = httpx.post(
            _URL,
            json={"api_key": settings.tavily_api_key, "query": query, "max_results": MAX_RESULTS},
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        logger.warning("Tavily search failed, treating as zero results: %s", exc)
        return []

    return [
        SearchResult(title=r.get("title", ""), url=r.get("url", ""), content=r.get("content", ""))
        for r in payload.get("results", [])
    ]
