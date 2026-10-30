"""Pydantic contracts for API requests and the final research report.

The development plan requires the Writer node to synthesize retrieved context
and MCP search results into a Pydantic schema. No concrete field list was
supplied in the PDF, so this schema maps directly to the LangGraph state fields
named in Milestone 3: user query, retrieved context, search results, and final report.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Research question to investigate.")


class TaskAccepted(BaseModel):
    task_id: str
    status: Literal["PENDING"] = "PENDING"


class TaskStatusResponse(BaseModel):
    task_id: str
    status: Literal["PENDING", "STARTED", "SUCCESS", "FAILURE", "RETRY", "REVOKED"]
    result: dict[str, Any] | None = None
    error: str | None = None


class SourceChunk(BaseModel):
    content: str
    source: str = "knowledge_base"
    score: float | None = None


class SearchHit(BaseModel):
    title: str
    snippet: str
    url: str | None = None


class ResearchReport(BaseModel):
    """Final structured output produced by the Writer node."""

    query: str
    summary: str = Field(..., description="Concise synthesis answering the query.")
    key_findings: list[str] = Field(default_factory=list)
    internal_context: list[SourceChunk] = Field(
        default_factory=list,
        description="Chunks retrieved from the vector database.",
    )
    external_results: list[SearchHit] = Field(
        default_factory=list,
        description="Results returned by the FastMCP web-search tool.",
    )
    confidence: Literal["low", "medium", "high"] = "medium"
