import pytest
from sqlalchemy import select

from app.config import config
from app.core.mail import sending
from app.modules.auth.models import User
from app.modules.notifications.service import notify
from tests.conftest import create_user, login

pytestmark = pytest.mark.modules("notifications")

API = "/api/v1/notifications"
RU = {"Accept-Language": "ru"}


async def _users(session_factory, *emails):
    async with session_factory() as session:
        return list(await session.scalars(select(User).where(User.email.in_(emails))))


async def _send(session_factory, emails, kind="lead_new", params=None, link="/admin/leads"):
    users = await _users(session_factory, *emails)
    async with session_factory() as session:
        await notify(session, users, kind, params or {"summary": "Ann"}, link)


@pytest.mark.anyio
async def test_list_in_request_language_and_mark_read(auth_client):
    client, session_factory = auth_client
    await create_user(session_factory, "ann@example.com", "user")
    await create_user(session_factory, "bob@example.com", "user")
    await _send(session_factory, ["ann@example.com", "bob@example.com"])
    await _send(session_factory, ["ann@example.com"], kind="unknown_kind", link=None)
    await login(client, "ann@example.com")

    page = (await client.get(API, headers=RU)).json()
    assert page["total"] == 2
    assert page["unread"] == 2
    newest, first = page["items"]
    assert (newest["title"], newest["body"]) == ("unknown_kind", "")
    assert (first["title"], first["body"], first["link"]) == ("Новая заявка", "Ann", "/admin/leads")
    assert (await client.get(API)).json()["items"][1]["title"] == "New lead"

    response = await client.post(f"{API}/{first['id']}/read")
    assert response.json()["read"] is True
    assert (await client.get(f"{API}/unread")).json() == {"unread": 1}
    assert (await client.get(API, params={"unread_only": True})).json()["total"] == 1

    assert (await client.post(f"{API}/read")).json() == {"unread": 0}
    assert (await client.get(f"{API}/unread")).json() == {"unread": 0}

    assert (await client.delete(f"{API}/{first['id']}")).status_code == 204
    assert (await client.get(API)).json()["total"] == 1


@pytest.mark.anyio
async def test_other_users_notifications_are_hidden(auth_client):
    client, session_factory = auth_client
    await create_user(session_factory, "ann@example.com", "user")
    await create_user(session_factory, "bob@example.com", "user")
    await _send(session_factory, ["ann@example.com"])
    await login(client, "ann@example.com")
    item = (await client.get(API)).json()["items"][0]

    await login(client, "bob@example.com")
    assert (await client.get(API)).json()["total"] == 0
    assert (await client.post(f"{API}/{item['id']}/read")).status_code == 404
    assert (await client.delete(f"{API}/{item['id']}")).status_code == 404


@pytest.mark.anyio
async def test_guests_get_401(auth_client):
    client, _ = auth_client
    assert (await client.get(f"{API}/unread")).status_code == 401


@pytest.mark.anyio
async def test_blocked_users_are_skipped(auth_client):
    client, session_factory = auth_client
    await create_user(session_factory, "ann@example.com", "user")
    async with session_factory() as session:
        ann = await session.scalar(select(User))
        ann.is_active = False
        await session.commit()
    await _send(session_factory, ["ann@example.com"])
    async with session_factory() as session:
        ann = await session.scalar(select(User))
        ann.is_active = True
        await session.commit()
    await login(client, "ann@example.com")
    assert (await client.get(API)).json()["total"] == 0


@pytest.mark.anyio
async def test_email_channel(auth_client, monkeypatch, eager_tasks):
    _, session_factory = auth_client
    sent = []
    monkeypatch.setitem(sending.BACKENDS, "console", sent.append)
    monkeypatch.setattr(config, "NOTIFICATIONS_CHANNELS", "in_app,email,pigeon")
    await create_user(session_factory, "ann@example.com", "user")
    sent.clear()  # the sign-up confirmation

    await _send(session_factory, ["ann@example.com"])

    (message,) = sent
    assert message.to == "ann@example.com"
    assert message.subject == "New lead"
    assert message.text.endswith(f"{config.FRONTEND_URL}/admin/leads")


CONTACT = {
    "name": "Анна",
    "email": "anna@example.com",
    "message": "Call me back please",
    "consent": True,
}


# Leads come from the admin module
@pytest.mark.anyio
@pytest.mark.modules("admin")
async def test_admins_are_notified_of_new_leads(auth_client):
    client, session_factory = auth_client
    await create_user(session_factory, "mod@example.com", "moderator")
    await create_user(session_factory, "user@example.com", "user")
    response = await client.post("/api/v1/forms/contact", json=CONTACT)
    assert response.status_code == 200, response.text

    await login(client, "mod@example.com")
    (item,) = (await client.get(API, headers=RU)).json()["items"]
    assert (item["title"], item["body"], item["link"]) == (
        "Новая заявка",
        "Анна · anna@example.com",
        "/admin/leads",
    )
    await login(client, "user@example.com")
    assert (await client.get(API)).json()["total"] == 0


@pytest.mark.anyio
@pytest.mark.modules("admin")
async def test_notification_failure_does_not_fail_the_form(auth_client, monkeypatch):
    from app.modules.leads import service as lead_service

    client, _ = auth_client

    async def broken(*args, **kwargs):
        raise RuntimeError("notifications are down")

    monkeypatch.setattr(lead_service, "_notify_admins", broken)
    response = await client.post("/api/v1/forms/contact", json=CONTACT)
    assert response.status_code == 200
