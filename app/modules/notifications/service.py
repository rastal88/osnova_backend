import logging
from collections.abc import Iterable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.auth.roles import Role
from app.modules.notifications.channels import enabled_channels
from app.modules.notifications.models import Notification

logger = logging.getLogger(__name__)


async def notify(
    session: AsyncSession,
    users: Iterable[User],
    kind: str,
    params: dict[str, Any] | None = None,
    link: str | None = None,
) -> None:
    """Notify active users: a row for the bell, then the other enabled channels.
    Texts: "notifications.<kind>.title" / ".body" in the locales, with `params`."""
    params = params or {}
    recipients = [user for user in users if user.is_active]
    session.add_all(
        Notification(user_id=user.id, kind=kind, params=params, link=link) for user in recipients
    )
    await session.commit()
    for channel in enabled_channels():
        for user in recipients:
            try:
                await channel(user, kind, params, link)
            except Exception:
                logger.exception("Notification %s to %s failed", kind, user.id)


async def users_with_roles(session: AsyncSession, *roles: Role) -> list[User]:
    return list(await session.scalars(select(User).where(User.role.in_(roles))))
