from __future__ import annotations

import time

from app.agent.graph import build_research_graph
from app.celery_app import celery_app
from app.config import get_settings
from app.rag.retrieve import get_cached_report, set_cached_report


@celery_app.task(bind=True, name="research.run")
def run_research_task(self, query: str) -> dict:
    """Celery research job: mock sleep (Milestone 1) then LangGraph pipeline."""
    settings = get_settings()

    # Milestone 1: observable PENDING window before work completes.
    time.sleep(settings.research_mock_sleep_seconds)

    cached = get_cached_report(query)
    if cached is not None:
        # Older cache entries may be report-only; normalize shape.
        if isinstance(cached, dict) and "report" in cached:
            return {**cached, "cached": True}
        return {"cached": True, "report": cached, "kb_sufficient": None, "used_web_search": None}

    final_state = build_research_graph().invoke({"query": query})
    report = final_state["final_report"]
    report_payload = report.model_dump() if hasattr(report, "model_dump") else report

    payload = {
        "cached": False,
        "report": report_payload,
        "kb_sufficient": bool(final_state.get("kb_sufficient")),
        "used_web_search": bool(final_state.get("used_web_search")),
    }
    set_cached_report(query, payload)
    return payload
