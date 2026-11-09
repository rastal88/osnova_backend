import pytest
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

from app.modules.auth.manager import UserManager
from app.modules.auth.models import User
from app.modules.auth.roles import Role
from app.modules.auth.schemas import UserCreate


async def _register(client, email: str, password: str):
    return await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )


async def _login(client, email: str, password: str):
    return await client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )


@pytest.mark.anyio
async def test_register_forces_user_role(auth_client):
    client, _ = auth_client

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "evil@example.com",
            "password": "password123",
            "role": "root",
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["role"] == "user"


@pytest.mark.anyio
async def test_login_and_current_user(auth_client):
    client, _ = auth_client

    await _register(client, "user@example.com", "password123")
    login = await _login(client, "user@example.com", "password123")
    assert login.status_code == 204, login.text

    me = await client.get("/api/v1/auth/users/me")
    assert me.status_code == 200, me.text
    assert me.json()["email"] == "user@example.com"
    assert me.json()["role"] == "user"


async def _create(session_factory, email: str, role: Role) -> None:
    async with session_factory() as session:
        manager = UserManager(SQLAlchemyUserDatabase(session, User))
        user = await manager.create(UserCreate(email=email, password="password123"))
        await manager.user_db.update(user, {"role": role})
        await session.commit()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("role", "areas", "admin_status"),
    [
        (Role.USER, ["client"], 403),
        (Role.MODERATOR, ["admin", "client"], 200),
        (Role.ROOT, ["admin", "client"], 200),
    ],
)
async def test_areas_by_role(auth_client, role, areas, admin_status):
    client, session_factory = auth_client
    await _create(session_factory, "someone@example.com", role)
    await _login(client, "someone@example.com", "password123")

    me = await client.get("/api/v1/auth/users/me")
    assert me.json()["areas"] == areas

    assert (await client.get("/api/v1/client/summary")).status_code == 200
    for path in ("/api/v1/admin/overview", "/api/v1/admin/users"):
        assert (await client.get(path)).status_code == admin_status


@pytest.mark.anyio
@pytest.mark.parametrize(
    "path", ["/api/v1/admin/overview", "/api/v1/admin/users", "/api/v1/client/summary"]
)
async def test_guest_gets_401(auth_client, path):
    client, _ = auth_client
    assert (await client.get(path)).status_code == 401


@pytest.mark.anyio
async def test_admin_overview_counts_users(auth_client):
    client, session_factory = auth_client
    await _create(session_factory, "root@example.com", Role.ROOT)
    await _create(session_factory, "moderator@example.com", Role.MODERATOR)
    await _register(client, "user@example.com", "password123")
    await _login(client, "root@example.com", "password123")

    overview = (await client.get("/api/v1/admin/overview")).json()
    assert overview == {
        "users": 3,
        "active_users": 3,
        "users_by_role": {"root": 1, "moderator": 1, "user": 1},
    }

    users = (await client.get("/api/v1/admin/users")).json()
    assert [item["email"] for item in users] == [
        "moderator@example.com",
        "root@example.com",
        "user@example.com",
    ]


@pytest.mark.anyio
async def test_create_superuser_gets_root_role(auth_client):
    client, session_factory = auth_client

    async with session_factory() as session:
        manager = UserManager(SQLAlchemyUserDatabase(session, User))
        await manager.create_superuser({"email": "root@example.com", "password": "password123"})
        await session.commit()

    login = await _login(client, "root@example.com", "password123")
    assert login.status_code == 204, login.text
    assert (await client.get("/api/v1/auth/users/me")).json()["role"] == "root"
