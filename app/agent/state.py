from typing import Any, TypedDict

from app.schemas import ResearchReport, SearchHit, SourceChunk


class ResearchState(TypedDict, total=False):
    """LangGraph state fields required by Milestone 3."""

    query: str
    retrieved_context: list[SourceChunk]
    search_results: list[SearchHit]
    kb_sufficient: bool
    used_web_search: bool
    final_report: ResearchReport | dict[str, Any]
