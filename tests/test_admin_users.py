import pytest
from sqlalchemy import select

from app.modules.auth.models import User
from tests.conftest import create_user, login

USERS = "/api/v1/admin/users"


async def _setup(auth_client, admin_role: str):
    """An admin signed in, plus a root, a moderator and three users."""
    client, session_factory = auth_client
    if admin_role != "root":
        await create_user(session_factory, "root@example.com", "root")
    await create_user(session_factory, f"admin-{admin_role}@example.com", admin_role)
    await create_user(session_factory, "mod@example.com", "moderator")
    for name in ("alice", "bob", "carol"):
        await create_user(session_factory, f"{name}@example.com", "user")
    await login(client, f"admin-{admin_role}@example.com")
    return client, session_factory


async def _id(session_factory, email: str) -> str:
    async with session_factory() as session:
        return str(await session.scalar(select(User.id).where(User.email == email)))


def _emails(response) -> list[str]:
    return [item["email"] for item in response.json()["items"]]


@pytest.mark.anyio
async def test_search_filters_sort_and_pages(auth_client):
    client, _ = await _setup(auth_client, "root")

    response = await client.get(USERS, params={"sort": "email", "size": 2, "page": 2})
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 5
    assert _emails(response) == ["bob@example.com", "carol@example.com"]

    response = await client.get(USERS, params={"q": "AL", "sort": "email"})
    assert _emails(response) == ["alice@example.com"]

    response = await client.get(USERS, params={"role": "moderator,root,unknown", "sort": "-email"})
    assert _emails(response) == ["mod@example.com", "admin-root@example.com"]

    # "_" is a literal character, not a LIKE wildcard
    assert (await client.get(USERS, params={"q": "_"})).json()["total"] == 0

    assert (await client.get(USERS, params={"sort": "password"})).status_code == 422
    assert (await client.get(USERS, params={"size": 1000})).status_code == 422


@pytest.mark.anyio
async def test_root_blocks_and_changes_role(auth_client):
    client, session_factory = await _setup(auth_client, "root")
    bob = await _id(session_factory, "bob@example.com")

    response = await client.patch(f"{USERS}/{bob}", json={"is_active": False})
    assert response.status_code == 200, response.text
    assert response.json()["is_active"] is False

    response = await client.get(USERS, params={"status": "blocked"})
    assert _emails(response) == ["bob@example.com"]

    response = await client.patch(f"{USERS}/{bob}", json={"is_active": True, "role": "moderator"})
    assert response.json()["role"] == "moderator"
    assert response.json()["is_active"] is True

    # There is one root: it is not assigned here
    response = await client.patch(f"{USERS}/{bob}", json={"role": "root"})
    assert response.status_code == 422


@pytest.mark.anyio
async def test_nobody_changes_self_or_root(auth_client):
    client, session_factory = await _setup(auth_client, "root")
    me = await _id(session_factory, "admin-root@example.com")

    response = await client.patch(f"{USERS}/{me}", json={"is_active": False})
    assert response.status_code == 403
    assert response.json()["code"] == "admin_cannot_change_self"

    client, session_factory = auth_client
    await login(client, "mod@example.com")
    response = await client.patch(f"{USERS}/{me}", json={"is_active": False})
    assert response.json()["code"] == "admin_root_protected"


@pytest.mark.anyio
async def test_moderator_blocks_only_users(auth_client):
    client, session_factory = await _setup(auth_client, "moderator")
    alice = await _id(session_factory, "alice@example.com")
    mod = await _id(session_factory, "mod@example.com")

    response = await client.patch(f"{USERS}/{alice}", json={"is_active": False})
    assert response.status_code == 200, response.text

    assert (await client.patch(f"{USERS}/{mod}", json={"is_active": False})).status_code == 403
    response = await client.patch(f"{USERS}/{alice}", json={"role": "moderator"})
    assert response.status_code == 403


@pytest.mark.anyio
async def test_blocked_user_loses_access(auth_client):
    client, session_factory = await _setup(auth_client, "root")
    alice = await _id(session_factory, "alice@example.com")

    await login(client, "alice@example.com")
    assert (await client.get("/api/v1/user/summary")).status_code == 200

    await login(client, "admin-root@example.com")
    await client.patch(f"{USERS}/{alice}", json={"is_active": False})

    response = await login(client, "alice@example.com")
    assert response.status_code == 400
    assert response.json()["code"] == "login_bad_credentials"


@pytest.mark.anyio
async def test_unknown_user_is_404(auth_client):
    client, _ = await _setup(auth_client, "root")
    response = await client.patch(
        f"{USERS}/00000000-0000-0000-0000-000000000000", json={"is_active": False}
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_search_by_name(auth_client):
    client, session_factory = await _setup(auth_client, "root")
    async with session_factory() as session:
        alice = await session.scalar(select(User).where(User.email == "alice@example.com"))
        alice.name = "Alice Liddell"
        await session.commit()
    items = (await client.get(USERS, params={"q": "liddell"})).json()["items"]
    assert [(item["email"], item["name"]) for item in items] == [
        ("alice@example.com", "Alice Liddell")
    ]
