from celery import shared_task
import logging

logger = logging.getLogger(__name__)

@shared_task(name="app.workers.tasks.send_notification_task")
def send_notification_task(user_id: str, message: str):
    logger.info(f"Sending notification to user {user_id}: {message}")
    return f"Notification sent to {user_id}"
