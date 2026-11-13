import pytest
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

from app.modules.auth.manager import UserManager
from app.modules.auth.models import User
from app.modules.auth.roles import Role
from app.modules.auth.schemas import UserCreate

pytestmark = pytest.mark.modules("auth")


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
        (Role.USER, ["user"], 403),
        (Role.MODERATOR, ["admin", "user"], 200),
        (Role.ROOT, ["admin", "user"], 200),
    ],
)
async def test_areas_by_role(auth_client, role, areas, admin_status):
    client, session_factory = auth_client
    await _create(session_factory, "someone@example.com", role)
    await _login(client, "someone@example.com", "password123")

    me = await client.get("/api/v1/auth/users/me")
    assert me.json()["areas"] == areas

    assert (await client.get("/api/v1/user/summary")).status_code == 200
    for path in ("/api/v1/admin/overview", "/api/v1/admin/users"):
        assert (await client.get(path)).status_code == admin_status


@pytest.mark.anyio
@pytest.mark.parametrize(
    "path", ["/api/v1/admin/overview", "/api/v1/admin/users", "/api/v1/user/summary"]
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


@pytest.mark.anyio
async def test_sign_in_is_rate_limited(auth_client):
    client, _ = auth_client
    for _ in range(10):
        assert (await _login(client, "nobody@example.com", "password123")).status_code == 400
    response = await _login(client, "nobody@example.com", "password123")
    assert response.status_code == 429
    assert response.json()["code"] == "too_many_requests"
    assert int(response.headers["Retry-After"]) > 0
    # Other endpoints count on their own
    response = await client.post("/api/v1/auth/forgot-password", json={"email": "a@example.com"})
    assert response.status_code == 202


@pytest.mark.parametrize("value", [None, "", "change-me", "short-key"])
def test_weak_secret_key_stops_the_start(value):
    from app.modules.auth.backend import check_secret_key

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        check_secret_key(value)
    check_secret_key("x" * 32)


def test_manage_py_keeps_createroot_as_a_command():
    from typer.testing import CliRunner

    from manage import app as cli

    result = CliRunner().invoke(cli, ["createroot", "--help"])
    assert result.exit_code == 0, result.output
