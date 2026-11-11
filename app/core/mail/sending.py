import asyncio
import logging
import smtplib
import ssl
from collections.abc import Awaitable, Callable
from email.message import EmailMessage as MimeMessage

from fastapi.concurrency import run_in_threadpool

from app.core.mail.message import EmailMessage
from app.core.mail.settings import MailSettings
from app.core.settings import settings

logger = logging.getLogger(__name__)

Backend = Callable[[EmailMessage], None]
Dispatcher = Callable[[EmailMessage], Awaitable[None]]


def _console(message: EmailMessage) -> None:
    logger.info(
        "Email (console backend, not sent)\nTo: %s\nSubject: %s\n\n%s",
        message.to,
        message.subject,
        message.text,
    )


def _smtp(message: EmailMessage) -> None:
    current = settings.get(MailSettings)
    mime = MimeMessage()
    mime["From"] = current.from_address
    mime["To"] = message.to
    mime["Subject"] = message.subject
    mime.set_content(message.text)
    if message.html:
        mime.add_alternative(message.html, subtype="html")

    address = (current.smtp_host, current.smtp_port)
    if current.smtp_security == "ssl":
        context = ssl.create_default_context()
        client = smtplib.SMTP_SSL(*address, timeout=current.smtp_timeout, context=context)
    else:
        client = smtplib.SMTP(*address, timeout=current.smtp_timeout)
    with client:
        if current.smtp_security == "starttls":
            client.starttls(context=ssl.create_default_context())
        if current.smtp_username:
            client.login(current.smtp_username, current.smtp_password)
        client.send_message(mime)


BACKENDS: dict[str, Backend] = {"console": _console, "smtp": _smtp}


def deliver(message: EmailMessage) -> None:
    """Send now, in this thread, as set in Admin → Settings → Mail (raises on failure)."""
    BACKENDS[settings.get(MailSettings).backend](message)


# Keeps background sends alive until they finish
_running: set[asyncio.Task] = set()


async def _deliver_logged(message: EmailMessage) -> None:
    try:
        await run_in_threadpool(deliver, message)
    except Exception:
        logger.exception("Could not send email to %s", message.to)


async def _in_background(message: EmailMessage) -> None:
    """Send in a thread without waiting: a slow mail server does not delay the response,
    and the response time does not tell whether an email was sent (password reset)."""
    task = asyncio.create_task(_deliver_logged(message))
    _running.add(task)
    task.add_done_callback(_running.discard)


_dispatcher: Dispatcher = _in_background


def use_dispatcher(dispatcher: Dispatcher) -> None:
    """Replace how send_mail hands messages over (the tasks module uses a queue)."""
    global _dispatcher
    _dispatcher = dispatcher


async def send_mail(message: EmailMessage) -> None:
    try:
        await _dispatcher(message)
    except Exception:
        logger.exception("Could not send email to %s", message.to)
