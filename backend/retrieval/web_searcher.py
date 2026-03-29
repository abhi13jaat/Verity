import logging

import httpx

from backend.core.config import settings

log = logging.getLogger("verity.retrieval.web")


def search_web(query: str, max_results: int = 5) -> list[dict]:
    """Search the web for relevant content.

    Uses Tavily if TAVILY_API_KEY is configured (best quality).
    Falls back to DuckDuckGo Instant Answer API (no key needed, limited).
    Returns list of {"title": ..., "url": ..., "content": ...}.
    """
    if settings.tavily_api_key:
        return _tavily_search(query, max_results)
    return _duckduckgo_search(query, max_results)


def _tavily_search(query: str, max_results: int) -> list[dict]:
    from tavily import TavilyClient
    log.info("[web] Tavily search | query=%r", query[:60])
    try:
        client = TavilyClient(api_key=settings.tavily_api_key)
        response = client.search(
            query=query,
            max_results=max_results,
            search_depth="advanced",
            include_raw_content=False,
        )
        results = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
            }
            for r in response.get("results", [])
        ]
        log.info("[web] Tavily returned %d results", len(results))
        return results
    except Exception as exc:
        log.warning("[web] Tavily failed: %s", exc)
        return []


def _duckduckgo_search(query: str, max_results: int) -> list[dict]:
    """DuckDuckGo Search — fallback scraper."""
    log.info("[web] DuckDuckGo search | query=%r", query[:60])
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "content": r.get("body", ""),
                })
        log.info("[web] DuckDuckGo returned %d results", len(results))
        return results
    except Exception as exc:
        log.warning("[web] DuckDuckGo failed: %s", exc)
        return []
