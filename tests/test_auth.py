import pytest
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

from app.modules.auth.manager import UserManager
from app.modules.auth.models import User


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


@pytest.mark.anyio
async def test_regular_user_cannot_access_admin(auth_client):
    client, _ = auth_client

    await _register(client, "user@example.com", "password123")
    await _login(client, "user@example.com", "password123")

    response = await client.get("/api/v1/admin_flow/users")
    assert response.status_code == 403


@pytest.mark.anyio
async def test_root_can_access_admin(auth_client):
    client, session_factory = auth_client

    async with session_factory() as session:
        manager = UserManager(SQLAlchemyUserDatabase(session, User))
        await manager.create_superuser({"email": "root@example.com", "password": "password123"})
        await session.commit()

    login = await _login(client, "root@example.com", "password123")
    assert login.status_code == 204, login.text

    me = await client.get("/api/v1/auth/users/me")
    assert me.status_code == 200
    assert me.json()["role"] == "root"

    users = await client.get("/api/v1/admin_flow/users")
    assert users.status_code == 200, users.text
    emails = [item["email"] for item in users.json()]
    assert "root@example.com" in emails


@pytest.mark.anyio
async def test_unauthenticated_admin_is_401(auth_client):
    client, _ = auth_client

    response = await client.get("/api/v1/admin_flow/users")
    assert response.status_code == 401


@pytest.mark.anyio
async def test_user_flow_open_to_any_signed_in_role(auth_client):
    client, session_factory = auth_client

    async with session_factory() as session:
        manager = UserManager(SQLAlchemyUserDatabase(session, User))
        await manager.create_superuser({"email": "root@example.com", "password": "password123"})
        await session.commit()

    await _login(client, "root@example.com", "password123")
    response = await client.get("/api/v1/user_flow/main")
    assert response.status_code == 200, response.text
    assert response.json()["role"] == "root"
