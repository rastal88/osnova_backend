"""The user's language: set at sign-up, changed in the profile; emails and
notifications go in it."""

import pytest
from sqlalchemy import select, update

from app.config import config
from app.core import i18n
from app.core.languages import Language, Languages
from app.core.mail import EmailMessage, sending
from app.modules.auth.models import User
from app.modules.tasks.celery_app import celery_app
from tests.conftest import create_user, login

pytestmark = [pytest.mark.anyio, pytest.mark.modules("auth")]

REGISTER = "/api/v1/auth/register"
USERS_ME = "/api/v1/auth/users/me"
CONTACT = {
    "name": "Ann",
    "email": "visitor@example.com",
    "message": "Call me back please",
    "consent": True,
}


@pytest.fixture
def outbox(monkeypatch):
    sent: list[EmailMessage] = []
    monkeypatch.setitem(sending.BACKENDS, "console", sent.append)
    monkeypatch.setattr(celery_app.conf, "task_always_eager", True)
    return sent


async def _set_language(session_factory, email: str, language: str | None) -> None:
    async with session_factory() as session:
        await session.execute(update(User).where(User.email == email).values(language=language))
        await session.commit()


def test_user_language_falls_back_to_the_request(monkeypatch):
    token = i18n.current_language.set("ru")
    try:
        assert i18n.user_language("en") == "en"
        assert i18n.user_language(None) == "ru"
        # A language switched off later
        only_ru = Languages(enabled=(Language("ru", "Русский"),), default="ru")
        monkeypatch.setattr(i18n, "get_languages", lambda: only_ru)
        assert i18n.user_language("en") == "ru"
    finally:
        i18n.current_language.reset(token)


async def test_sign_up_keeps_the_request_language(auth_client, outbox):
    client, session_factory = auth_client
    response = await client.post(
        REGISTER,
        json={"email": "new@example.com", "password": "password123"},
        headers={"Accept-Language": "ru"},
    )
    assert response.status_code == 201, response.text
    async with session_factory() as session:
        statement = select(User.language).where(User.email == "new@example.com")
        language = await session.scalar(statement)
    assert language == "ru"


async def test_language_is_changed_in_the_profile(auth_client):
    client, session_factory = auth_client
    await create_user(session_factory, "ann@example.com", "user")
    await login(client, "ann@example.com")

    response = await client.patch(USERS_ME, json={"language": "ru"})
    assert response.status_code == 200, response.text
    assert response.json()["language"] == "ru"
    assert (await client.get(USERS_ME)).json()["language"] == "ru"

    response = await client.patch(USERS_ME, json={"language": "de"})
    assert response.status_code == 422
    (error,) = response.json()["fields"]
    assert (error["field"], error["code"]) == ("language", "language_not_enabled")


async def test_account_emails_go_in_the_user_language(auth_client, outbox):
    client, session_factory = auth_client
    await create_user(session_factory, "ann@example.com", "user")
    await _set_language(session_factory, "ann@example.com", "ru")
    outbox.clear()

    # Asked from an English page: the email and its link are still in Russian
    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "ann@example.com"},
        headers={"Accept-Language": "en"},
    )
    assert response.status_code == 202, response.text
    (message,) = outbox
    assert f"{config.FRONTEND_URL}/ru/reset-password?token=" in message.text
    assert 'lang="ru"' in message.html


async def test_notification_emails_go_in_each_recipient_language(auth_client, outbox, monkeypatch):
    client, session_factory = auth_client
    monkeypatch.setattr(config, "NOTIFICATIONS_CHANNELS", "in_app,email")
    await create_user(session_factory, "ru@example.com", "moderator")
    await create_user(session_factory, "en@example.com", "moderator")
    await _set_language(session_factory, "ru@example.com", "ru")
    await _set_language(session_factory, "en@example.com", "en")
    outbox.clear()

    # A visitor from a Russian page; each admin reads in their own language
    response = await client.post(
        "/api/v1/forms/contact", json=CONTACT, headers={"Accept-Language": "ru"}
    )
    assert response.status_code == 200, response.text

    subjects = {message.to: message.subject for message in outbox if "@example.com" in message.to}
    assert subjects["en@example.com"] == "New lead"
    assert subjects["ru@example.com"] != "New lead"
