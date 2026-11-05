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
)
