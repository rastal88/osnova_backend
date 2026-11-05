"""Background tasks module: Celery app and example task.

Enabled by BACKGROUND_TASKS_ENABLED. Requires CELERY_BROKER_URL.
Worker: ``celery -A app.modules.tasks.celery_app worker -l info``
Requirements: requirements/tasks.txt
"""

from fastapi import FastAPI


def register(app: FastAPI):
    # Importing configures the Celery app so tasks can be sent from endpoints.
    from .celery_app import celery_app  # noqa: F401

    return None
