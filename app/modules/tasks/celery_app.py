from importlib.util import find_spec

from celery import Celery
from celery.schedules import crontab
from celery.signals import setup_logging, task_prerun

from app.config import config

if not config.CELERY_BROKER_URL:
    raise RuntimeError("Background tasks module requires CELERY_BROKER_URL")

# Task modules of the optional packages that are present (a deleted module is skipped)
TASK_MODULES = ("app.modules.tasks.tasks", "app.modules.leads.tasks")

celery_app = Celery(
    "osnova",
    broker=config.CELERY_BROKER_URL,
    backend=config.CELERY_RESULT_BACKEND or config.CELERY_BROKER_URL,
    include=[name for name in TASK_MODULES if find_spec(name)],
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
    # The worker keeps trying to reach the broker at start (the default, said explicitly
    # to keep Celery from warning about a coming change)
    broker_connection_retry_on_startup=True,
    task_publish_retry_policy={"max_retries": 2, "interval_start": 0, "interval_step": 0.2},
)


@setup_logging.connect
def use_app_logging(**_) -> None:
    """The worker and beat log like the web process (text or JSON, LOG_FORMAT) instead
    of Celery's own format."""
    from app.core.logging_config import setup_logging as setup

    setup()


@task_prerun.connect
def load_admin_settings(**_) -> None:
    """Settings changed in the admin (mail, retention, site name) reach the worker too."""
    from app.core.modules import resolve_enabled

    if "settings" in {spec.name for spec in resolve_enabled(config)}:
        from app.modules.settings.service import refresh_stored_settings

        refresh_stored_settings()


# Tasks on a schedule, sent by `celery beat` (one instance: the `beat` service in Docker
# Compose). Times are UTC. Add an entry with the task name and a crontab or seconds.
if config.DATABASE_URL:
    celery_app.conf.beat_schedule = {
        "cleanup": {"task": "maintenance.cleanup", "schedule": crontab(hour=3, minute=30)},
    }
