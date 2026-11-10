"""Where notifications go besides the bell: NOTIFICATIONS_CHANNELS="in_app,email".

The in-app channel (the `notifications` table) is always on. A channel is an
async function ``(user, kind, params, link) -> None``; add one to CHANNELS
(e.g. Telegram with a chat id stored for the user) and list it in the setting.
Channels must not raise: a failure is logged and the others still run.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.config import config
from app.core.mail import EmailMessage, render_html, send_mail
from app.modules.auth.models import User
from app.modules.notifications.texts import render

logger = logging.getLogger(__name__)

Channel = Callable[[User, str, dict[str, Any], str | None], Awaitable[None]]


async def email_channel(user: User, kind: str, params: dict[str, Any], link: str | None) -> None:
    title, body = render(kind, params)
    url = f"{config.FRONTEND_URL.rstrip('/')}{link}" if link else None
    if url:
        body = f"{body}\n\n{url}"
    html = render_html(body, title, link=url)
    await send_mail(EmailMessage(to=user.email, subject=title, text=body, html=html))


CHANNELS: dict[str, Channel] = {"email": email_channel}


def enabled_channels() -> list[Channel]:
    names = [name.strip() for name in config.NOTIFICATIONS_CHANNELS.split(",") if name.strip()]
    unknown = [name for name in names if name != "in_app" and name not in CHANNELS]
    if unknown:
        logger.warning("Unknown NOTIFICATIONS_CHANNELS: %s", ", ".join(unknown))
    return [CHANNELS[name] for name in names if name in CHANNELS]
