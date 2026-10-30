"""Retrieve top-K chunks for a query, with optional Redis semantic cache."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import redis

from app.config import get_settings
from app.rag.store import get_vectorstore
from app.schemas import SourceChunk


def _cache_client() -> redis.Redis:
    settings = get_settings()
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


def _cache_key(query: str) -> str:
    digest = hashlib.sha256(query.strip().lower().encode("utf-8")).hexdigest()
    return f"semantic_cache:retrieval:{digest}"


def retrieve_chunks(query: str, top_k: int | None = None) -> list[SourceChunk]:
    settings = get_settings()
    k = top_k or settings.top_k

    if settings.semantic_cache_enabled:
        cached = _get_cached_retrieval(query)
        if cached is not None:
            return cached

    vectorstore = get_vectorstore(create_if_missing=False)
    docs_with_scores = vectorstore.similarity_search_with_score(query, k=k)

    chunks: list[SourceChunk] = []
    for doc, score in docs_with_scores:
        chunks.append(
            SourceChunk(
                content=doc.page_content,
                source=str(doc.metadata.get("source", "knowledge_base")),
                score=float(score),
            )
        )

    if settings.semantic_cache_enabled:
        _set_cached_retrieval(query, chunks)

    return chunks


def _get_cached_retrieval(query: str) -> list[SourceChunk] | None:
    client = _cache_client()
    raw = client.get(_cache_key(query))
    if not raw:
        return None
    payload: list[dict[str, Any]] = json.loads(raw)
    return [SourceChunk.model_validate(item) for item in payload]


def _set_cached_retrieval(query: str, chunks: list[SourceChunk]) -> None:
    settings = get_settings()
    client = _cache_client()
    client.setex(
        _cache_key(query),
        settings.semantic_cache_ttl_seconds,
        json.dumps([c.model_dump() for c in chunks]),
    )


def get_cached_report(query: str) -> dict[str, Any] | None:
    """Bonus: cache full research reports to skip repeat LLM runs."""
    settings = get_settings()
    if not settings.semantic_cache_enabled:
        return None
    client = _cache_client()
    digest = hashlib.sha256(query.strip().lower().encode("utf-8")).hexdigest()
    raw = client.get(f"semantic_cache:report:{digest}")
    if not raw:
        return None
    return json.loads(raw)


def set_cached_report(query: str, report: dict[str, Any]) -> None:
    settings = get_settings()
    if not settings.semantic_cache_enabled:
        return
    client = _cache_client()
    digest = hashlib.sha256(query.strip().lower().encode("utf-8")).hexdigest()
    client.setex(
        f"semantic_cache:report:{digest}",
        settings.semantic_cache_ttl_seconds,
        json.dumps(report),
    )
