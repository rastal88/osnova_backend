from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.modules.auth.models import User
from app.modules.auth.roles import Role


async def cleanup(session: AsyncSession) -> int:
    """Remove accounts whose email was never confirmed, UNVERIFIED_ACCOUNT_DAYS after
    sign-up (0: keep them); see app/modules/db/cleanup.py.

    Only ordinary users who have never signed in: an account that changed its email
    is also unconfirmed for a while, but it has signed in and may own data.
    """
    if config.UNVERIFIED_ACCOUNT_DAYS <= 0:
        return 0
    before = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=config.UNVERIFIED_ACCOUNT_DAYS)
    result = await session.execute(
        delete(User).where(
            User.is_verified.is_(False),
            User.role == Role.USER,
            User.last_login.is_(None),
            User.date_created < before,
        )
    )
    return result.rowcount
