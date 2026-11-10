import asyncio
import logging
import smtplib
import ssl
from collections.abc import Awaitable, Callable
from email.message import EmailMessage as MimeMessage

from fastapi.concurrency import run_in_threadpool

from app.config import config
from app.core.mail.message import EmailMessage

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
    mime = MimeMessage()
    mime["From"] = config.MAIL_FROM
    mime["To"] = message.to
    mime["Subject"] = message.subject
    mime.set_content(message.text)

    address = (config.SMTP_HOST, config.SMTP_PORT)
    if config.SMTP_SECURITY == "ssl":
        context = ssl.create_default_context()
        client = smtplib.SMTP_SSL(*address, timeout=config.SMTP_TIMEOUT, context=context)
    else:
        client = smtplib.SMTP(*address, timeout=config.SMTP_TIMEOUT)
    with client:
        if config.SMTP_SECURITY == "starttls":
            client.starttls(context=ssl.create_default_context())
        if config.SMTP_USERNAME:
            client.login(config.SMTP_USERNAME, config.SMTP_PASSWORD or "")
        client.send_message(mime)


BACKENDS: dict[str, Backend] = {"console": _console, "smtp": _smtp}


def deliver(message: EmailMessage) -> None:
    """Send now, in this thread, with MAIL_BACKEND (raises on failure)."""
    BACKENDS[config.MAIL_BACKEND](message)


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
