from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.modules.notifications.models import Notification


async def cleanup(session: AsyncSession) -> int:
    """Remove read notifications created more than NOTIFICATIONS_KEEP_DAYS ago
    (unread ones stay); see app/modules/db/cleanup.py."""
    if config.NOTIFICATIONS_KEEP_DAYS <= 0:
        return 0
    before = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=config.NOTIFICATIONS_KEEP_DAYS)
    result = await session.execute(
        delete(Notification).where(
            Notification.read_at.is_not(None), Notification.created_at < before
        )
    )
    return result.rowcount
