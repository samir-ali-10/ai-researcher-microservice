"""LangGraph execution nodes: Retriever, Researcher, Writer."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Literal

from pydantic import ValidationError

from app.agent.state import ResearchState
from app.config import get_settings
from app.llm import get_chat_model
from app.rag.retrieve import retrieve_chunks
from app.schemas import ResearchReport, SearchHit, SourceChunk

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def kb_is_sufficient(query: str, chunks: list[SourceChunk]) -> bool:
    """Return True when retrieved KB context looks relevant enough to skip web search."""
    if not chunks:
        return False

    settings = get_settings()
    distances = [c.score for c in chunks if c.score is not None]
    if distances and min(distances) > settings.kb_max_distance:
        return False

    query_tokens = {t.lower() for t in _TOKEN_RE.findall(query) if len(t) > 2}
    if not query_tokens:
        return True

    haystack = " ".join(c.content for c in chunks).lower()
    overlap = sum(1 for token in query_tokens if token in haystack)
    return overlap >= settings.kb_min_token_overlap


def retriever_node(state: ResearchState) -> dict[str, Any]:
    """Retriever Node: call the vector database for top-K chunks."""
    chunks = retrieve_chunks(state["query"])
    sufficient = kb_is_sufficient(state["query"], chunks)
    return {
        "retrieved_context": chunks,
        "kb_sufficient": sufficient,
        "used_web_search": False,
        "search_results": [],
    }


def route_after_retrieve(state: ResearchState) -> Literal["researcher", "writer"]:
    """If KB cannot answer, go to Researcher (live web via FastMCP); else write."""
    if state.get("kb_sufficient"):
        return "writer"
    return "researcher"


def researcher_node(state: ResearchState) -> dict[str, Any]:
    """Researcher Node: use the FastMCP web_search tool for external data."""
    results = asyncio.run(_call_web_search(state["query"]))
    # If an old MCP process is still serving mock example.com hits, search live directly.
    if _looks_like_stale_mock(results):
        results = _direct_live_search(state["query"], limit=5)
    return {"search_results": results, "used_web_search": True}


def _looks_like_stale_mock(results: list[SearchHit]) -> bool:
    if not results:
        return False
    return all((h.url or "").startswith("https://example.com/") for h in results)


def _direct_live_search(query: str, limit: int = 5) -> list[SearchHit]:
    from app.mcp_server.server import _live_search

    return [SearchHit.model_validate(item) for item in _live_search(query, limit)]


async def _call_web_search(query: str) -> list[SearchHit]:
    settings = get_settings()
    from fastmcp import Client

    client = Client(settings.mcp_server_url)
    async with client:
        raw = await client.call_tool("web_search", {"query": query, "limit": 5})

    payload = _normalize_mcp_result(raw)
    return [SearchHit.model_validate(item) for item in payload]


def _normalize_mcp_result(raw: Any) -> list[dict[str, Any]]:
    """Normalize FastMCP / MCP client return shapes into a list of dicts."""
    if raw is None:
        return []

    if hasattr(raw, "data") and raw.data is not None:
        data = raw.data
        if isinstance(data, list):
            return [dict(item) if not isinstance(item, dict) else item for item in data]
        if isinstance(data, dict):
            return [data]

    if hasattr(raw, "content"):
        texts: list[str] = []
        for block in raw.content:
            text = getattr(block, "text", None)
            if text:
                texts.append(text)
        if texts:
            parsed = json.loads(texts[0])
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                return [parsed]

    if isinstance(raw, list):
        return [dict(item) if not isinstance(item, dict) else item for item in raw]
    if isinstance(raw, dict):
        return [raw]
    if isinstance(raw, str):
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            return [parsed]
    raise TypeError(f"Unexpected MCP tool result type: {type(raw)!r}")


def writer_node(state: ResearchState) -> dict[str, Any]:
    """Writer Node: synthesize vector context + MCP results into ResearchReport."""
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for the Writer node.")

    context_chunks: list[SourceChunk] = list(state.get("retrieved_context") or [])
    search_hits: list[SearchHit] = list(state.get("search_results") or [])
    used_web = bool(state.get("used_web_search"))
    kb_ok = bool(state.get("kb_sufficient"))

    llm = get_chat_model(temperature=0).with_structured_output(ResearchReport)

    prompt = (
        "You are a research report writer. Produce a ResearchReport that answers the query.\n"
        "Use ONLY the internal vector-database context and external web/MCP search results provided.\n"
        "Prefer internal KB context when it is relevant. Use web results when the KB is insufficient.\n"
        "If evidence is thin, lower confidence and say so in the summary.\n\n"
        f"Query: {state['query']}\n"
        f"KB judged sufficient: {kb_ok}\n"
        f"Web search used: {used_web}\n\n"
        f"Internal context (JSON):\n{json.dumps([c.model_dump() for c in context_chunks], ensure_ascii=False)}\n\n"
        f"External search results (JSON):\n{json.dumps([h.model_dump() for h in search_hits], ensure_ascii=False)}\n"
    )

    report = llm.invoke(prompt)
    if isinstance(report, ResearchReport):
        report.internal_context = context_chunks
        report.external_results = search_hits
        return {"final_report": report}

    try:
        validated = ResearchReport.model_validate(report)
    except ValidationError as exc:
        validated = ResearchReport(
            query=state["query"],
            summary="Structured generation failed validation; returning grounded fallback.",
            key_findings=[str(exc)[:200]],
            internal_context=context_chunks,
            external_results=search_hits,
            confidence="low",
        )
    else:
        validated.internal_context = context_chunks
        validated.external_results = search_hits
    return {"final_report": validated}
