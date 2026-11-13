import asyncio
import logging
import threading
from urllib.parse import parse_qs, urlparse

import pytest

from app.config import config
from app.core.mail import (
    EmailMessage,
    render_html,
    render_mail,
    send_mail,
    sending,
    use_dispatcher,
)
from tests.conftest import login, register


@pytest.fixture
def outbox(monkeypatch, eager_tasks):
    """Messages "sent" by the console backend; Celery runs tasks inline."""
    sent: list[EmailMessage] = []
    monkeypatch.setitem(sending.BACKENDS, "console", sent.append)
    yield sent


def _token(message: EmailMessage) -> str:
    link = next(line for line in message.text.splitlines() if line.startswith("http"))
    return parse_qs(urlparse(link).query)["token"][0]


def test_render_mail_in_language():
    message = render_mail("verify_email", "a@example.com", "ru", site="Acme", link="http://x")
    assert message.subject == "Подтвердите email для Acme"
    assert "http://x" in message.text


def test_console_backend_logs_message(caplog):
    with caplog.at_level(logging.INFO, logger="app.core.mail.sending"):
        sending.deliver(EmailMessage(to="a@example.com", subject="Hi", text="Body"))
    assert "To: a@example.com" in caplog.text
    assert "Body" in caplog.text


def test_smtp_backend(monkeypatch):
    calls = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls.append(("connect", host, port))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def starttls(self, context):
            calls.append(("starttls",))

        def login(self, username, password):
            calls.append(("login", username, password))

        def send_message(self, mime):
            calls.append(("send", mime["From"], mime["To"], mime["Subject"]))

    monkeypatch.setattr(sending.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(config, "MAIL_BACKEND", "smtp")
    monkeypatch.setattr(config, "SMTP_HOST", "mail.example.com")
    monkeypatch.setattr(config, "SMTP_USERNAME", "robot")
    monkeypatch.setattr(config, "SMTP_PASSWORD", "secret")

    sending.deliver(EmailMessage(to="a@example.com", subject="Hi", text="Body"))

    assert calls == [
        ("connect", "mail.example.com", 587),
        ("starttls",),
        ("login", "robot", "secret"),
        ("send", config.MAIL_FROM, "a@example.com", "Hi"),
    ]


@pytest.mark.anyio
async def test_send_mail_logs_failures(caplog):
    async def broken(message):
        raise ConnectionError("mail server is down")

    previous = sending._dispatcher
    use_dispatcher(broken)
    try:
        with caplog.at_level(logging.ERROR):
            await send_mail(EmailMessage(to="a@example.com", subject="Hi", text="Body"))
    finally:
        use_dispatcher(previous)
    assert "Could not send email to a@example.com" in caplog.text


@pytest.mark.anyio
async def test_without_queue_mail_is_sent_after_returning(monkeypatch, caplog):
    sent: list[EmailMessage] = []
    release = threading.Event()

    def slow(message: EmailMessage) -> None:
        release.wait(5)
        sent.append(message)

    monkeypatch.setitem(sending.BACKENDS, "console", slow)
    message = EmailMessage(to="a@example.com", subject="Hi", text="Body")
    await sending._in_background(message)
    assert sent == []  # returned before the mail server answered
    release.set()
    await asyncio.gather(*sending._running)
    assert sent == [message]

    def broken(message: EmailMessage) -> None:
        raise ConnectionError("down")

    monkeypatch.setitem(sending.BACKENDS, "console", broken)
    with caplog.at_level(logging.ERROR):
        await sending._in_background(message)
        await asyncio.gather(*sending._running)
    assert "Could not send email to a@example.com" in caplog.text


@pytest.mark.anyio
@pytest.mark.modules("auth")
async def test_sign_up_sends_confirmation(auth_client, outbox):
    client, _ = auth_client

    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "new@example.com", "password": "password123"},
        headers={"Accept-Language": "ru"},
    )
    assert response.status_code == 201, response.text

    (message,) = outbox
    assert message.to == "new@example.com"
    assert message.subject == "Подтвердите email для TestApp"
    assert f"{config.FRONTEND_URL}/ru/verify-email?token=" in message.text

    response = await client.post("/api/v1/auth/verify", json={"token": _token(message)})
    assert response.status_code == 200, response.text
    assert response.json()["is_verified"] is True


@pytest.mark.anyio
@pytest.mark.modules("auth")
async def test_password_reset_by_email(auth_client, outbox):
    client, _ = auth_client
    await register(client, "user@example.com")
    outbox.clear()

    response = await client.post("/api/v1/auth/forgot-password", json={"email": "user@example.com"})
    assert response.status_code == 202
    (message,) = outbox
    assert "/en/reset-password?token=" in message.text

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": _token(message), "password": "new-password-1"},
    )
    assert response.status_code == 200, response.text
    assert (await login(client, "user@example.com", "new-password-1")).status_code == 204

    # Unknown addresses get the same answer and no email
    outbox.clear()
    response = await client.post("/api/v1/auth/forgot-password", json={"email": "no@example.com"})
    assert response.status_code == 202
    assert outbox == []


def test_html_version_has_layout_button_and_escapes():
    from app.core.settings import settings
    from app.settings import SiteSettings

    settings.set(SiteSettings(name="Acme & <Co>"))
    link = "http://x/verify?token=a&b=1"
    message = render_mail("verify_email", "a@example.com", "ru", site="Acme", link=link)

    assert link in message.text
    assert '<html lang="ru">' in message.html
    assert "Acme &amp; &lt;Co&gt;" in message.html
    assert "<Co>" not in message.html
    assert 'href="http://x/verify?token=a&amp;b=1"' in message.html
    assert ">Подтвердить email</a>" in message.html
    assert "$" not in message.html

    # A message without a link has no button; only web links become one
    assert "<a " not in render_mail("email_changed", "a@example.com", site="Acme").html
    assert "<a " not in render_html("Hi\n\njavascript:x", "S", link="javascript:x")
    html = render_html("<b>one</b>\ntwo\n\nthree", "Subject")
    assert "&lt;b&gt;one&lt;/b&gt;<br>two</p>" in html
    assert html.count("<p ") == 2


def test_smtp_sends_text_and_html(monkeypatch):
    sent = []

    class FakeSMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def starttls(self, context):
            pass

        def send_message(self, mime):
            sent.append(mime)

    monkeypatch.setattr(sending.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(config, "MAIL_BACKEND", "smtp")

    sending.deliver(render_mail("reset_password", "a@example.com", site="Acme", link="http://x"))
    sending.deliver(EmailMessage(to="a@example.com", subject="Hi", text="Body"))

    with_html, text_only = sent
    assert with_html.get_content_type() == "multipart/alternative"
    assert [part.get_content_type() for part in with_html.iter_parts()] == [
        "text/plain",
        "text/html",
    ]
    assert "Set a new password" in with_html.get_body(("html",)).get_content()
    assert text_only.get_content_type() == "text/plain"


def test_queued_message_keeps_html_and_old_payloads_work():
    message = EmailMessage(to="a@example.com", subject="Hi", text="Body", html="<p>Body</p>")
    assert EmailMessage(**message.to_dict()) == message
    # A task queued before the HTML version existed
    assert EmailMessage(to="a@example.com", subject="Hi", text="Body").html is None
