"""Tasks run by the worker: ``celery -A app.modules.tasks.celery_app worker -l info``.

Add a task here (or in a module of its own listed in celery_app ``include``) and
call it with ``task.delay(...)``; arguments must be JSON-serialisable. To run a task
on a schedule, list it in ``beat_schedule`` (celery_app.py).
"""

import asyncio
import logging
import smtplib

from app.core.mail import EmailMessage, deliver
from app.modules.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


# Bound to celery_app (not shared_task): calls from other threads use its settings
@celery_app.task(
    name="mail.send",
    # Nobody reads the result; also keeps sending free of the result backend
    ignore_result=True,
    autoretry_for=(OSError, smtplib.SMTPException),
    retry_backoff=True,
    max_retries=5,
)
def send_mail_task(message: dict[str, str]) -> None:
    """Example task: send an email built with app.core.mail, retrying while the server is down."""
    deliver(EmailMessage(**message))


@celery_app.task(name="maintenance.cleanup", ignore_result=True)
def cleanup_task() -> None:
    """Example scheduled task: remove old rows every night (app/modules/db/cleanup.py)."""
    # Imported here: the tasks module also works without a database
    from app.modules.db.cleanup import run_cleanup

    asyncio.run(run_cleanup())
