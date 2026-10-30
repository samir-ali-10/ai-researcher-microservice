"""Celery discovery entrypoint: `celery -A tasks worker --pool=solo --loglevel=INFO`."""

from app.celery_app import celery_app
from app.tasks import run_research_task

# Celery CLI looks for an attribute named `app` (or `celery`) on the target module.
app = celery_app

__all__ = ["app", "celery_app", "run_research_task"]
