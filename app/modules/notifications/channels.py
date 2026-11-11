"""Where notifications go besides the bell: chosen in Admin → Settings → Notifications
(NOTIFICATIONS_CHANNELS in .env is the initial value).

The in-app channel (the `notifications` table) is always on. A channel is an
async function ``(user, kind, params, link) -> None``; add one to CHANNELS
(e.g. Telegram with a chat id stored for the user): it becomes an option of the setting.
Channels must not raise: a failure is logged and the others still run.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.config import config
from app.core.i18n import user_language
from app.core.mail import EmailMessage, render_html, send_mail
from app.modules.auth.models import User
from app.modules.notifications.texts import render

logger = logging.getLogger(__name__)

Channel = Callable[[User, str, dict[str, Any], str | None], Awaitable[None]]


async def email_channel(user: User, kind: str, params: dict[str, Any], link: str | None) -> None:
    # In the recipient's language, not the one of the request that caused it
    language = user_language(user.language)
    title, body = render(kind, params, language)
    url = f"{config.FRONTEND_URL.rstrip('/')}{link}" if link else None
    if url:
        body = f"{body}\n\n{url}"
    html = render_html(body, title, link=url, language=language)
    await send_mail(EmailMessage(to=user.email, subject=title, text=body, html=html))


CHANNELS: dict[str, Channel] = {"email": email_channel}


def enabled_channels() -> list[Channel]:
    """The channels chosen in Admin → Settings → Notifications."""
    from app.core.settings import settings
    from app.modules.notifications.settings import NotificationSettings

    return [CHANNELS[name] for name in settings.get(NotificationSettings).channels]
