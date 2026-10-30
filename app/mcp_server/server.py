"""FastMCP server exposing a Web Search tool for external/dynamic context.

Uses live DuckDuckGo search by default. Falls back to the small mock corpus
if the live search fails (network/rate-limit), so the agent still gets a response.
"""

from __future__ import annotations

import logging
import os

from fastmcp import FastMCP

logger = logging.getLogger(__name__)

mcp = FastMCP("ai-researcher-tools")

# Used only when live search is disabled or fails.
_MOCK_CORPUS = [
    {
        "title": "Async workers and message brokers",
        "snippet": (
            "Celery with Redis separates API request handling from long-running jobs. "
            "Clients poll task status instead of waiting on the HTTP response."
        ),
        "url": "https://example.com/async-workers",
        "keywords": ["celery", "redis", "async", "worker", "broker", "task"],
    },
    {
        "title": "Retrieval-augmented generation overview",
        "snippet": (
            "RAG embeds documents into a vector database and retrieves top-K chunks "
            "so an LLM answers with grounded internal context."
        ),
        "url": "https://example.com/rag",
        "keywords": ["rag", "vector", "embedding", "retrieval", "chunk", "chroma"],
    },
    {
        "title": "Model Context Protocol tools",
        "snippet": (
            "MCP servers expose tools such as web search to agents. FastMCP makes it "
            "straightforward to host those tools over stdio or HTTP."
        ),
        "url": "https://example.com/mcp",
        "keywords": ["mcp", "fastmcp", "tool", "agent", "github"],
    },
    {
        "title": "LangGraph multi-step research agents",
        "snippet": (
            "LangGraph StateGraph nodes can retrieve context, call external tools, "
            "and write a structured final report in separate steps."
        ),
        "url": "https://example.com/langgraph",
        "keywords": ["langgraph", "agent", "state", "research", "writer"],
    },
]


def _mock_search(query: str, limit: int) -> list[dict]:
    tokens = {t.lower() for t in query.replace(",", " ").split() if t}
    scored: list[tuple[int, dict]] = []
    for item in _MOCK_CORPUS:
        score = sum(1 for kw in item["keywords"] if any(kw in token or token in kw for token in tokens))
        if score == 0 and tokens:
            haystack = f"{item['title']} {item['snippet']}".lower()
            score = sum(1 for token in tokens if token in haystack)
        scored.append((score, item))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    results: list[dict] = []
    for score, item in scored[: max(1, limit)]:
        if score == 0 and results:
            break
        results.append({"title": item["title"], "snippet": item["snippet"], "url": item["url"]})
    if not results:
        results = [
            {"title": item["title"], "snippet": item["snippet"], "url": item["url"]}
            for item in _MOCK_CORPUS[: max(1, limit)]
        ]
    return results


def _live_search(query: str, limit: int) -> list[dict]:
    from ddgs import DDGS

    results: list[dict] = []
    with DDGS() as ddgs:
        for item in ddgs.text(query, max_results=max(1, limit)):
            results.append(
                {
                    "title": item.get("title") or "Untitled",
                    "snippet": item.get("body") or item.get("snippet") or "",
                    "url": item.get("href") or item.get("url"),
                }
            )
    return results


@mcp.tool
def web_search(query: str, limit: int = 5) -> list[dict]:
    """Search the live web for material related to the query.

    Returns up to `limit` hits with title, snippet, and url.
    """
    mode = os.getenv("WEB_SEARCH_MODE", "live").strip().lower()
    if mode == "mock":
        return _mock_search(query, limit)

    try:
        live = _live_search(query, limit)
        if live:
            return live
        logger.warning("Live web search returned no results for query=%r", query)
        return []
    except Exception as exc:
        logger.exception("Live web search failed for query=%r", query)
        # Do not fall back to the unrelated mock corpus — that misleads the Writer.
        return [
            {
                "title": "Web search error",
                "snippet": f"Live web search failed: {exc}",
                "url": None,
            }
        ]


if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8001)
