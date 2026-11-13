import importlib.util
import uuid
from pathlib import Path

import pytest

from app.modules.auth.dependencies import require, users_with_permission
from app.modules.auth.models import RoleRecord
from app.modules.auth.permissions import all_permissions, permission
from tests.conftest import MODERATOR_PERMISSIONS, create_user, login

pytestmark = [pytest.mark.anyio, pytest.mark.modules("admin")]

ME = "/api/v1/auth/users/me"
LEADS = "/api/v1/admin/leads"
USERS = "/api/v1/admin/users"


async def _signed_in(auth_client, role: str, permissions: list[str] | None = None):
    client, session_factory = auth_client
    if permissions is not None:
        async with session_factory() as session:
            session.add(RoleRecord(slug=role, name=role.title(), permissions=permissions))
            await session.commit()
    await create_user(session_factory, f"{role}@example.com", role)
    await login(client, f"{role}@example.com")
    return client, session_factory


def test_names_are_checked():
    with pytest.raises(ValueError, match="area.action"):
        permission("Leads")
    with pytest.raises(ValueError, match="Unknown permission: leads.raed"):
        require("leads.raed")


def test_moderator_seed_matches_the_migration():
    path = Path(__file__).resolve().parent.parent / "migrations/versions/0009_roles.py"
    spec = importlib.util.spec_from_file_location("migration_0009", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.MODERATOR == MODERATOR_PERMISSIONS
    assert set(MODERATOR_PERMISSIONS) <= all_permissions()


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("user", []),
        ("moderator", sorted(MODERATOR_PERMISSIONS)),
        ("root", sorted(all_permissions())),
    ],
)
async def test_me_lists_permissions(auth_client, role, expected):
    client, _ = await _signed_in(auth_client, role)
    me = (await client.get(ME)).json()
    assert me["role"] == role
    assert me["permissions"] == expected
    assert "settings.mail" in all_permissions()


async def test_role_from_the_database_allows_only_its_actions(auth_client):
    # A permission of a module that is not there is ignored
    client, _ = await _signed_in(
        auth_client, "sales", ["admin.access", "leads.read", "shop.orders"]
    )
    me = (await client.get(ME)).json()
    assert me["role"] == "sales"
    assert me["permissions"] == ["admin.access", "leads.read"]
    assert me["areas"] == ["admin", "user"]

    assert (await client.get(LEADS)).status_code == 200
    assert (await client.get(f"{LEADS}/export")).status_code == 403
    assert (await client.delete(f"{LEADS}/{uuid.uuid4()}")).status_code == 403
    assert (await client.get(USERS)).status_code == 403
    assert (await client.put("/api/v1/admin/settings/site", json={})).status_code == 403


async def test_permission_without_admin_access_does_not_open_the_admin(auth_client):
    client, _ = await _signed_in(auth_client, "reader", ["users.read"])
    assert (await client.get(ME)).json()["areas"] == ["user"]
    assert (await client.get(USERS)).status_code == 403

    client, _ = await _signed_in(auth_client, "outside", ["leads.read"])
    assert (await client.get(LEADS)).status_code == 403


async def test_blocking_staff_needs_the_roles_permission(auth_client):
    client, session_factory = await _signed_in(auth_client, "moderator")
    await create_user(session_factory, "peer@example.com", "moderator")
    await create_user(session_factory, "ann@example.com", "user")
    users = {item["email"]: item["id"] for item in (await client.get(USERS)).json()["items"]}

    response = await client.patch(f"{USERS}/{users['peer@example.com']}", json={"is_active": False})
    assert response.status_code == 403
    response = await client.patch(f"{USERS}/{users['ann@example.com']}", json={"is_active": False})
    assert response.status_code == 200


async def test_users_with_permission(auth_client):
    _, session_factory = await _signed_in(auth_client, "sales", ["admin.access", "leads.read"])
    for role in ("root", "moderator", "user"):
        await create_user(session_factory, f"{role}@example.com", role)
    async with session_factory() as session:
        readers = await users_with_permission(session, "leads.read")
        managers = await users_with_permission(session, "settings.mail")
    assert {user.role for user in readers} == {"root", "moderator", "sales"}
    assert {user.role for user in managers} == {"root"}
