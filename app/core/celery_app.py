from celery import Celery
from app.config import config

def make_celery():
    celery = Celery(
        "workers",
        broker=config.CELERY_BROKER_URL,
        backend=config.CELERY_BROKER_URL,  # Для хранения результатов задач
        include=["app.workers.tasks"],  # Укажите модуль с задачами
    )

    celery.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
    )

    return celery