import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="tasks.send_notification")
def send_notification_task(user_id: str, message: str):
    logger.info("Sending notification to user %s: %s", user_id, message)
    return f"Notification sent to {user_id}"
