from pathlib import Path

from celery.result import AsyncResult
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.celery_app import celery_app
from app.schemas import ResearchRequest, TaskAccepted, TaskStatusResponse
from app.tasks import run_research_task

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="AI Research Microservice",
    description=(
        "Asynchronous AI research API: FastAPI accepts requests, Celery + Redis "
        "run long-running RAG + LangGraph research in the background."
    ),
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def ui() -> FileResponse:
    """Serve the research web UI."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/research", response_model=TaskAccepted, status_code=202)
def start_research(body: ResearchRequest) -> TaskAccepted:
    """Queue a research job and return task_id immediately (100% async)."""
    async_result = run_research_task.delay(body.query)
    return TaskAccepted(task_id=async_result.id)


@app.get("/api/v1/task/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str) -> TaskStatusResponse:
    """Reflect Celery PENDING / SUCCESS (and other) states for a task_id."""
    result = AsyncResult(task_id, app=celery_app)
    status = result.status

    if status == "SUCCESS":
        return TaskStatusResponse(task_id=task_id, status="SUCCESS", result=result.result)

    if status == "FAILURE":
        return TaskStatusResponse(
            task_id=task_id,
            status="FAILURE",
            error=str(result.result),
        )

    if status not in {"PENDING", "STARTED", "RETRY", "REVOKED"}:
        raise HTTPException(status_code=500, detail=f"Unexpected task status: {status}")

    return TaskStatusResponse(task_id=task_id, status=status)  # type: ignore[arg-type]
