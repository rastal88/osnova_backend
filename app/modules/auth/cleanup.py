from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.modules.auth.models import User
from app.modules.auth.roles import Role
from app.settings import RetentionSettings


async def cleanup(session: AsyncSession) -> int:
    """Remove accounts whose email was never confirmed, as many days after sign-up as
    Admin → Settings → Retention says (0: keep them); see app/modules/db/cleanup.py.

    Only ordinary users who have never signed in: an account that changed its email
    is also unconfirmed for a while, but it has signed in and may own data.
    """
    days = settings.get(RetentionSettings).unverified_account_days
    if days <= 0:
        return 0
    before = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)
    result = await session.execute(
        delete(User).where(
            User.is_verified.is_(False),
            User.role == Role.USER,
            User.last_login.is_(None),
            User.date_created < before,
        )
    )
    return result.rowcount
