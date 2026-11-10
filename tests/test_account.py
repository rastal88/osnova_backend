import time
from contextlib import asynccontextmanager
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.core.mail import EmailMessage, sending
from app.modules.auth import sessions
from app.modules.auth.models import OAuthAccount, User
from app.modules.files.models import FileRecord
from app.modules.notifications.models import Notification
from app.modules.notifications.service import notify
from app.modules.tasks.celery_app import celery_app
from tests.conftest import _app_with, create_user, login

ME = "/api/v1/auth/me"
USERS_ME = "/api/v1/auth/users/me"


@pytest.fixture
def outbox(monkeypatch):
    sent: list[EmailMessage] = []
    monkeypatch.setitem(sending.BACKENDS, "console", sent.append)
    monkeypatch.setattr(celery_app.conf, "task_always_eager", True)
    return sent


@asynccontextmanager
async def other_device(session_factory, email: str, monkeypatch):
    """A second browser, signed in a minute ago (sessions count whole seconds)."""
    async with AsyncClient(
        transport=ASGITransport(app=_app_with(session_factory)), base_url="http://test"
    ) as device:
        earlier = time.time() - 60
        with monkeypatch.context() as patch:
            patch.setattr(sessions.time, "time", lambda: earlier)
            assert (await login(device, email)).status_code == 204
        yield device


async def _signed_in(auth_client, email="ann@example.com", role="user"):
    client, session_factory = auth_client
    await create_user(session_factory, email, role)
    assert (await login(client, email)).status_code == 204
    return client, session_factory


async def _count(session_factory, model, *where) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count()).select_from(model).where(*where))


@pytest.mark.anyio
async def test_name_is_the_only_field_of_patch_me(auth_client):
    client, _ = await _signed_in(auth_client)

    response = await client.patch(USERS_ME, json={"name": "  Ann Smith "})
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Ann Smith"
    assert (await client.patch(USERS_ME, json={"name": ""})).json()["name"] is None

    # A stolen session cannot change the password or the email this way
    for field in ({"password": "new-password-1"}, {"email": "x@example.com"}):
        assert (await client.patch(USERS_ME, json=field)).status_code == 422


@pytest.mark.anyio
async def test_sign_up_with_a_name(auth_client):
    client, _ = auth_client
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "bob@example.com", "password": "password123", "name": "Bob"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["name"] == "Bob"


@pytest.mark.anyio
async def test_change_password_ends_other_sessions(auth_client, monkeypatch):
    client, session_factory = await _signed_in(auth_client)

    async with other_device(session_factory, "ann@example.com", monkeypatch) as device:
        response = await client.post(
            f"{ME}/password",
            json={"current_password": "wrong-password", "new_password": "new-password-1"},
        )
        assert response.status_code == 400
        assert response.json()["code"] == "current_password_wrong"

        response = await client.post(
            f"{ME}/password",
            json={"current_password": "password123", "new_password": "ann@example.com-1"},
        )
        assert response.json()["code"] == "password_contains_email"

        response = await client.post(
            f"{ME}/password",
            json={"current_password": "password123", "new_password": "new-password-1"},
        )
        assert response.status_code == 204, response.text
        # This browser stays signed in with a new cookie, the other one is out
        assert (await client.get(USERS_ME)).status_code == 200
        assert (await device.get(USERS_ME)).status_code == 401

    assert (await login(client, "ann@example.com")).status_code == 400
    assert (await login(client, "ann@example.com", "new-password-1")).status_code == 204


@pytest.mark.anyio
async def test_change_email_asks_for_confirmation(auth_client, outbox):
    client, session_factory = await _signed_in(auth_client)
    await create_user(session_factory, "taken@example.com", "user")

    response = await client.post(f"{ME}/email", json={"password": "bad", "email": "a@b.co"})
    assert response.json()["code"] == "current_password_wrong"
    response = await client.post(
        f"{ME}/email", json={"password": "password123", "email": "TAKEN@example.com"}
    )
    assert response.json()["code"] == "update_user_email_already_exists"

    response = await client.post(
        f"{ME}/email", json={"password": "password123", "email": "ann.new@example.com"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["email"] == "ann.new@example.com"
    assert response.json()["is_verified"] is False

    notice, confirm = outbox[-2:]
    assert notice.to == "ann@example.com"
    assert "changed" in notice.subject
    assert confirm.to == "ann.new@example.com"
    link = next(line for line in confirm.text.splitlines() if line.startswith("http"))
    token = parse_qs(urlparse(link).query)["token"][0]
    response = await client.post("/api/v1/auth/verify", json={"token": token})
    assert response.json()["is_verified"] is True


@pytest.mark.anyio
async def test_sign_out_everywhere(auth_client, monkeypatch):
    client, session_factory = await _signed_in(auth_client)
    async with other_device(session_factory, "ann@example.com", monkeypatch) as device:
        assert (await client.post(f"{ME}/sign-out-everywhere")).status_code == 204
        assert (await device.get(USERS_ME)).status_code == 401
    assert (await client.get(USERS_ME)).status_code == 401
    # Signing in again works
    assert (await login(client, "ann@example.com")).status_code == 204
    assert (await client.get(USERS_ME)).status_code == 200


@pytest.mark.anyio
async def test_password_reset_ends_sessions(auth_client, outbox, monkeypatch):
    client, session_factory = await _signed_in(auth_client)
    async with other_device(session_factory, "ann@example.com", monkeypatch) as device:
        await client.post("/api/v1/auth/forgot-password", json={"email": "ann@example.com"})
        link = next(line for line in outbox[-1].text.splitlines() if line.startswith("http"))
        token = parse_qs(urlparse(link).query)["token"][0]
        response = await client.post(
            "/api/v1/auth/reset-password", json={"token": token, "password": "new-password-1"}
        )
        assert response.status_code == 200, response.text
        assert (await device.get(USERS_ME)).status_code == 401


@pytest.mark.anyio
async def test_delete_account_with_its_data(auth_client, tmp_path):
    client, session_factory = await _signed_in(auth_client)
    upload = await client.post("/api/v1/files", files={"file": ("a.txt", b"hi", "text/plain")})
    assert upload.status_code == 201
    async with session_factory() as session:
        ann = await session.scalar(select(User).where(User.email == "ann@example.com"))
        await notify(session, [ann], "lead_new", {"summary": "x"})
    assert any(tmp_path.iterdir())

    response = await client.request("DELETE", ME, json={"password": "wrong"})
    assert response.json()["code"] == "account_delete_not_confirmed"
    # The email confirms only accounts that sign in with a provider
    response = await client.request("DELETE", ME, json={"email": "ann@example.com"})
    assert response.status_code == 400

    response = await client.request("DELETE", ME, json={"password": "password123"})
    assert response.status_code == 204, response.text
    assert await _count(session_factory, User, User.email == "ann@example.com") == 0
    assert await _count(session_factory, FileRecord) == 0
    assert await _count(session_factory, Notification) == 0
    assert not any(tmp_path.iterdir())
    assert (await client.get(USERS_ME)).status_code == 401


@pytest.mark.anyio
async def test_provider_account_confirms_deletion_with_its_email(auth_client):
    client, session_factory = await _signed_in(auth_client)
    async with session_factory() as session:
        ann = await session.scalar(select(User))
        session.add(
            OAuthAccount(
                user_id=ann.id,
                oauth_name="google",
                access_token="t",
                account_id="1",
                account_email="ann@example.com",
            )
        )
        await session.commit()

    response = await client.request("DELETE", ME, json={"email": " ANN@example.com "})
    assert response.status_code == 204, response.text
    assert await _count(session_factory, User) == 0
    assert await _count(session_factory, OAuthAccount) == 0


@pytest.mark.anyio
async def test_root_cannot_delete_itself(auth_client):
    client, _ = await _signed_in(auth_client, "root@example.com", "root")
    response = await client.request("DELETE", ME, json={"password": "password123"})
    assert response.status_code == 403
    assert response.json()["code"] == "root_cannot_delete_self"


@pytest.mark.anyio
async def test_account_endpoints_need_sign_in(client):
    assert (await client.post(f"{ME}/sign-out-everywhere")).status_code == 401
    assert (await client.request("DELETE", ME, json={"password": "x"})).status_code == 401


class FakeRedis:
    def __init__(self):
        self.data: dict[str, str] = {}

    async def set(self, key, value, ex=None):
        self.data[key] = value

    async def get(self, key):
        return self.data.get(key)

    async def delete(self, key):
        self.data.pop(key, None)


class Manager:
    def __init__(self, user):
        self.user = user

    def parse_id(self, value):
        return value

    async def get(self, user_id):
        return self.user


@pytest.mark.anyio
async def test_redis_sessions_end_too(monkeypatch):
    user = User(id="u1", email="a@example.com", hashed_password="x")
    redis = FakeRedis()
    strategy = sessions.SessionRedisStrategy(redis, lifetime_seconds=60)
    monkeypatch.setattr(sessions.time, "time", lambda: 1_000_000)
    token = await strategy.write_token(user)

    assert await strategy.read_token(token, Manager(user)) is user
    user.sessions_valid_after = sessions.datetime.fromtimestamp(1_000_001)
    user.sessions_valid_after = user.sessions_valid_after.astimezone(sessions.UTC).replace(
        tzinfo=None
    )
    assert await strategy.read_token(token, Manager(user)) is None
    # A session stored before this change (no time) also ends
    redis.data[f"{strategy.key_prefix}old"] = "u1"
    assert await strategy.read_token("old", Manager(user)) is None
