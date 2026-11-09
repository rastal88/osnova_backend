import logging
from urllib.parse import parse_qs, urlparse

import pytest

from app.config import config
from app.core.mail import EmailMessage, render_mail, send_mail, sending, use_dispatcher
from app.modules.tasks.celery_app import celery_app
from tests.conftest import login, register


@pytest.fixture
def outbox(monkeypatch):
    """Messages "sent" by the console backend; Celery runs tasks inline."""
    sent: list[EmailMessage] = []
    monkeypatch.setitem(sending.BACKENDS, "console", sent.append)
    monkeypatch.setattr(celery_app.conf, "task_always_eager", True)
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

    use_dispatcher(broken)
    try:
        with caplog.at_level(logging.ERROR):
            await send_mail(EmailMessage(to="a@example.com", subject="Hi", text="Body"))
    finally:
        use_dispatcher(sending._in_thread)
    assert "Could not send email to a@example.com" in caplog.text


@pytest.mark.anyio
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
