import asyncio
import hashlib
import hmac
import json
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import select

from app.config import config
from app.core.mail import sending
from app.modules.entities.models import Entity
from app.modules.leads import channels, delivery
from app.modules.leads.models import Lead
from tests.conftest import create_user, login

pytestmark = pytest.mark.modules("admin")

CONTACT = {
    "name": "Анна",
    "email": "anna@example.com",
    "topic": "order",
    "message": "Please call me back tomorrow",
    "consent": True,
}


@pytest.fixture
def posts(monkeypatch):
    """HTTP requests the channels make: (url, body, headers)."""
    sent: list[tuple[str, dict, dict]] = []

    def fake_post(url, body, headers=None):
        sent.append((url, json.loads(body), headers or {}))

    monkeypatch.setattr(channels, "_post_json", fake_post)
    return sent


@pytest.fixture
def in_process(monkeypatch):
    monkeypatch.setattr(config, "BACKGROUND_TASKS_ENABLED", False)


async def _add_channel(session_factory, type_: str, params: dict, name: str = "ch", enabled=True):
    async with session_factory() as session:
        entity = Entity(type=type_, name=name, params=params, enabled=enabled)
        session.add(entity)
        await session.commit()
        return str(entity.id)


async def _submit(client, language="ru"):
    response = await client.post(
        "/api/v1/forms/contact", json=CONTACT, headers={"Accept-Language": language}
    )
    assert response.status_code == 200, response.text
    await asyncio.gather(*delivery._running)


async def _lead(session_factory) -> Lead:
    async with session_factory() as session:
        return await session.scalar(select(Lead))


@pytest.mark.anyio
async def test_lead_goes_to_enabled_channels(auth_client, posts, in_process):
    client, session_factory = auth_client
    hook = await _add_channel(
        session_factory, "lead_webhook", {"url": "https://example.com/hook", "secret": "s3"}, "Hook"
    )
    tg = await _add_channel(
        session_factory, "lead_telegram", {"bot_token": "1:a", "chat_id": "42"}, "TG"
    )
    await _add_channel(
        session_factory, "lead_telegram", {"bot_token": "1:a", "chat_id": "9"}, "Off", False
    )

    await _submit(client)

    assert len(posts) == 2
    (tg_url, tg_body, _), (hook_url, hook_body, headers) = sorted(posts, key=lambda p: p[0])
    assert tg_url == "https://api.telegram.org/bot1:a/sendMessage"
    assert tg_body["chat_id"] == "42"
    assert tg_body["text"].splitlines()[0] == "Новая заявка: Связаться с нами"
    assert "Тема: Заказ" in tg_body["text"]
    assert "Я согласен на обработку персональных данных: Да" in tg_body["text"]

    assert hook_url == "https://example.com/hook"
    assert hook_body["data"]["name"] == "Анна"
    body = json.dumps(hook_body, ensure_ascii=False).encode()
    expected = hmac.new(b"s3", body, hashlib.sha256).hexdigest()
    assert headers["X-Osnova-Signature"] == f"sha256={expected}"

    lead = await _lead(session_factory)
    assert {key: value["status"] for key, value in lead.deliveries.items()} == {
        hook: "sent",
        tg: "sent",
    }


@pytest.mark.anyio
async def test_no_channels_no_delivery(auth_client, posts, in_process):
    client, session_factory = auth_client
    await _submit(client)
    assert posts == []
    assert (await _lead(session_factory)).deliveries == {}


@pytest.mark.anyio
async def test_failures_are_recorded_and_retried(auth_client, monkeypatch, in_process):
    client, session_factory = auth_client
    rejected = await _add_channel(session_factory, "lead_webhook", {"url": "https://a.test"}, "A")
    flaky = await _add_channel(session_factory, "lead_webhook", {"url": "https://b.test"}, "B")
    calls: list[str] = []
    b_attempts = [0]

    def fake_post(url, body, headers=None):
        calls.append(url)
        if url == "https://a.test":
            raise channels.DeliveryRejected("HTTP 404: no such hook")
        b_attempts[0] += 1
        if b_attempts[0] == 1:  # B fails on the first delivery only
            raise ConnectionError("timed out")

    monkeypatch.setattr(channels, "_post_json", fake_post)
    await _submit(client)

    lead = await _lead(session_factory)
    assert lead.deliveries[rejected]["error"] == "HTTP 404: no such hook"
    assert lead.deliveries[flaky]["status"] == "failed"

    assert lead.deliveries[rejected]["final"] is True

    # A retry sends only the channel that failed for a transient reason
    calls.clear()
    async with session_factory() as session:
        assert await delivery.deliver_lead(session, lead.id) is False
    assert calls == ["https://b.test"]
    lead = await _lead(session_factory)
    assert lead.deliveries[flaky]["status"] == "sent"
    assert lead.deliveries[rejected]["status"] == "failed"

    # Nothing is sent again once every channel is settled
    calls.clear()
    async with session_factory() as session:
        await delivery.deliver_lead(session, lead.id)
    assert calls == []


@pytest.mark.anyio
async def test_email_channel(auth_client, monkeypatch, in_process):
    client, session_factory = auth_client
    sent = []
    monkeypatch.setitem(sending.BACKENDS, "console", sent.append)
    await _add_channel(session_factory, "lead_email", {"to": "sales@example.com"})

    await _submit(client, "en")

    (message,) = sent
    assert message.to == "sales@example.com"
    assert message.subject == "New submission: Contact us"
    assert "Topic: Order" in message.text


@pytest.mark.anyio
@pytest.mark.modules("tasks")
async def test_celery_task_and_queue_fallback(auth_client, posts, monkeypatch, eager_tasks):
    from app.modules.leads import tasks

    client, session_factory = auth_client
    await _add_channel(session_factory, "lead_webhook", {"url": "https://example.com/hook"})

    @asynccontextmanager
    async def test_session():
        async with session_factory() as session:
            yield session

    monkeypatch.setattr(tasks, "standalone_session", test_session)
    await _submit(client)
    assert len(posts) == 1

    # The queue is down: delivered in process instead
    def broken_delay(*args):
        raise ConnectionError("broker is down")

    monkeypatch.setattr(tasks.deliver_lead_task, "delay", broken_delay)
    await _submit(client)
    assert len(posts) == 2


@pytest.mark.anyio
async def test_test_message(auth_client, posts, monkeypatch):
    client, session_factory = auth_client
    channel = await _add_channel(
        session_factory, "lead_telegram", {"bot_token": "1:a", "chat_id": "42"}
    )
    await create_user(session_factory, "root@example.com", "root")
    await login(client, "root@example.com")

    response = await client.post(f"/api/v1/admin/leads/channels/{channel}/test")
    assert response.json() == {"ok": True, "error": None}
    assert posts[0][1]["text"].startswith("Test message")

    def rejected(*args, **kwargs):
        raise channels.DeliveryRejected("HTTP 401: Unauthorized")

    monkeypatch.setattr(channels, "_post_json", rejected)
    response = await client.post(f"/api/v1/admin/leads/channels/{channel}/test")
    assert response.json() == {"ok": False, "error": "DeliveryRejected: HTTP 401: Unauthorized"}
