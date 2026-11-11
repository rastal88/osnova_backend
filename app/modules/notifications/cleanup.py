from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.modules.notifications.models import Notification
from app.settings import RetentionSettings


async def cleanup(session: AsyncSession) -> int:
    """Remove read notifications older than Admin → Settings → Retention says (unread
    ones stay; 0: keep them); see app/modules/db/cleanup.py."""
    days = settings.get(RetentionSettings).notifications_days
    if days <= 0:
        return 0
    before = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)
    result = await session.execute(
        delete(Notification).where(
            Notification.read_at.is_not(None), Notification.created_at < before
        )
    )
    return result.rowcount
