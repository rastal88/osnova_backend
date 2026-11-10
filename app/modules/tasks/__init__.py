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
    from app.core.readiness import add_check

    from .celery_app import celery_app
    from .tasks import send_mail_task

    def connect_to_broker() -> None:
        with celery_app.connection_for_write() as connection:
            connection.ensure_connection(max_retries=1)

    async def broker() -> None:
        # Without the broker no email is sent (leads fall back to in-process delivery)
        await run_in_threadpool(connect_to_broker)

    add_check("broker", broker)

    async def queue_mail(message: EmailMessage) -> None:
        # delay() talks to the broker synchronously: keep it off the event loop
        await run_in_threadpool(send_mail_task.delay, message.to_dict())

    use_dispatcher(queue_mail)
    return None
