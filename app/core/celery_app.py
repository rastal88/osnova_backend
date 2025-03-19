from celery import Celery
from app.config import config

celery = Celery(
    "workers",
    broker=config.CELERY_BROKER,
    backend=config.CELERY_BROKER,  # Для хранения результатов задач
    include=["app.workers.tasks"],  # Укажите модуль с задачами
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)