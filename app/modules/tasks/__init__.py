"""Background tasks module: Celery app, the worker and the email task.

Enabled by BACKGROUND_TASKS_ENABLED. Requires CELERY_BROKER_URL.
Worker: ``celery -A app.modules.tasks.celery_app worker -l info`` (the `worker`
service in Docker Compose for standard / scalable). When enabled, emails from
app.core.mail go through the queue instead of being sent in the web process.
Requirements: requirements/tasks.txt
"""

from fastapi import FastAPI


def register(app: FastAPI):
    from fastapi.concurrency import run_in_threadpool

    from app.core.mail import EmailMessage, use_dispatcher

    from .tasks import send_mail_task

    async def queue_mail(message: EmailMessage) -> None:
        # delay() talks to the broker synchronously: keep it off the event loop
        await run_in_threadpool(send_mail_task.delay, message.to_dict())

    use_dispatcher(queue_mail)
    return None
