from celery import Celery

from app.config import config

if not config.CELERY_BROKER_URL:
    raise RuntimeError("Background tasks module requires CELERY_BROKER_URL")

celery_app = Celery(
    "osnova",
    broker=config.CELERY_BROKER_URL,
    backend=config.CELERY_RESULT_BACKEND or config.CELERY_BROKER_URL,
    include=["app.modules.tasks.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # When the broker is down, sending a task fails in a fraction of a second instead of
    # blocking the request for many seconds (the worker reconnects on its own settings)
    broker_transport_options={"max_retries": 0},
    task_publish_retry_policy={"max_retries": 2, "interval_start": 0, "interval_step": 0.2},
)
