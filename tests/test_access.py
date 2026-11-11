"""Admin → Roles and groups, and giving them to users."""

import pytest
from sqlalchemy import select, update

from app.core.i18n import catalogs
from app.modules.auth import permissions
from app.modules.auth.dependencies import users_with_permission
from app.modules.auth.models import RoleRecord, User
from app.modules.auth.permissions import all_permissions
from tests.conftest import MODERATOR_PERMISSIONS, create_user, login

pytestmark = pytest.mark.anyio

ADMIN = "/api/v1/admin"
ROLES = f"{ADMIN}/roles"
GROUPS = f"{ADMIN}/groups"
USERS = f"{ADMIN}/users"
ME = "/api/v1/auth/users/me"


async def _root(auth_client):
    client, session_factory = auth_client
    await create_user(session_factory, "root@example.com", "root")
    await login(client, "root@example.com")
    return client, session_factory


async def _id(session_factory, email: str) -> str:
    async with session_factory() as session:
        return str(await session.scalar(select(User.id).where(User.email == email)))


async def _sign_in(client, email: str) -> None:
    client.cookies.clear()
    assert (await login(client, email)).status_code == 204


async def test_every_permission_has_texts():
    for language, catalog in catalogs.items():
        for name in all_permissions():
            assert name in catalog["permissions"], (language, name)
            assert name.partition(".")[0] in catalog["permission_areas"], (language, name)


async def test_permissions_are_listed_with_texts(auth_client):
    client, _ = await _root(auth_client)
    response = await client.get(f"{ADMIN}/permissions", headers={"Accept-Language": "ru"})
    items = {item["name"]: item for item in response.json()}
    assert set(items) == all_permissions()
    assert items["leads.read"] == {
        "name": "leads.read",
        "title": "Просмотр заявок",
        "area": "leads",
        "area_title": "Заявки",
        "everyone": False,
    }


async def test_role_lifecycle(auth_client):
    client, session_factory = await _root(auth_client)

    roles = {role["slug"]: role for role in (await client.get(ROLES)).json()}
    assert list(roles) == ["moderator", "root", "user"]
    assert roles["root"]["permissions"] == sorted(all_permissions())
    assert roles["root"]["users"] == 1
    assert roles["moderator"]["permissions"] == sorted(MODERATOR_PERMISSIONS)

    response = await client.post(
        ROLES, json={"name": "Sales team", "permissions": ["leads.read", "admin.access"]}
    )
    assert response.status_code == 201, response.text
    assert response.json() == {
        "slug": "sales-team",
        "name": "Sales team",
        "permissions": ["admin.access", "leads.read"],
        "system": False,
        "users": 0,
    }
    # The slug stays unique; a name without Latin letters still gets one
    assert (await client.post(ROLES, json={"name": "Sales team"})).json()["slug"] == "sales-team-2"
    assert (await client.post(ROLES, json={"name": "Продажи"})).json()["slug"] == "role"

    response = await client.put(
        f"{ROLES}/sales-team", json={"name": "Sales", "permissions": ["leads.read"]}
    )
    assert response.json()["name"] == "Sales"
    assert response.json()["permissions"] == ["leads.read"]

    response = await client.post(ROLES, json={"name": "Typo", "permissions": ["leads.raed"]})
    assert response.status_code == 400
    assert response.json()["code"] == "permission_unknown"

    # A role that users have is not deleted
    await create_user(session_factory, "ann@example.com", "sales-team")
    response = await client.delete(f"{ROLES}/sales-team")
    assert (response.status_code, response.json()["code"]) == (409, "role_in_use")
    ann = await _id(session_factory, "ann@example.com")
    assert (await client.patch(f"{USERS}/{ann}", json={"role": "user"})).status_code == 200
    assert (await client.delete(f"{ROLES}/sales-team")).status_code == 204
    assert (await client.delete(f"{ROLES}/sales-team")).status_code == 404


async def test_built_in_roles_are_protected(auth_client):
    client, _ = await _root(auth_client)

    for request in (
        client.put(f"{ROLES}/root", json={"permissions": []}),
        client.delete(f"{ROLES}/root"),
        client.delete(f"{ROLES}/moderator"),
        client.put(f"{ROLES}/user", json={"name": "Customer"}),
    ):
        response = await request
        assert (response.status_code, response.json()["code"]) == (403, "role_protected")

    # Their permissions are edited (root aside)
    response = await client.put(
        f"{ROLES}/moderator", json={"permissions": ["admin.access", "leads.read"]}
    )
    assert response.json()["permissions"] == ["admin.access", "leads.read"]


async def test_permissions_of_a_disabled_module_survive_an_edit(auth_client):
    from app.modules.auth.models import RoleRecord

    client, session_factory = await _root(auth_client)
    async with session_factory() as session:
        session.add(RoleRecord(slug="shop", name="Shop", permissions=["shop.orders", "leads.read"]))
        await session.commit()

    response = await client.put(f"{ROLES}/shop", json={"permissions": ["admin.access"]})
    assert response.json()["permissions"] == ["admin.access"]
    async with session_factory() as session:
        role = await session.get(RoleRecord, "shop")
        assert role.permissions == ["admin.access", "shop.orders"]


async def test_groups_give_their_roles(auth_client):
    client, session_factory = await _root(auth_client)
    await create_user(session_factory, "ann@example.com", "user")
    ann = await _id(session_factory, "ann@example.com")
    await client.post(ROLES, json={"name": "Sales", "permissions": ["admin.access", "leads.read"]})
    await client.post(ROLES, json={"name": "Export", "permissions": ["leads.export"]})

    response = await client.post(GROUPS, json={"name": "Office", "roles": ["sales", "export"]})
    assert response.status_code == 201, response.text
    group = response.json()
    assert (group["name"], group["roles"], group["users"]) == ("Office", ["export", "sales"], 0)
    response = await client.post(GROUPS, json={"name": "Office"})
    assert (response.status_code, response.json()["code"]) == (409, "name_taken")
    response = await client.post(GROUPS, json={"name": "Owners", "roles": ["root"]})
    assert (response.status_code, response.json()["code"]) == (403, "role_protected")
    response = await client.post(GROUPS, json={"name": "Ghosts", "roles": ["nope"]})
    assert (response.status_code, response.json()["code"]) == (400, "role_unknown")

    response = await client.patch(f"{USERS}/{ann}", json={"groups": [group["id"]]})
    assert response.status_code == 200, response.text
    assert response.json()["groups"] == [group["id"]]
    assert response.json()["role"] == "user"
    assert (await client.get(GROUPS)).json()[0]["users"] == 1
    listed = (await client.get(USERS, params={"group": f"{group['id']},not-an-id"})).json()
    assert [item["email"] for item in listed["items"]] == ["ann@example.com"]

    async with session_factory() as session:
        readers = await users_with_permission(session, "leads.read")
    assert {user.email for user in readers} == {"root@example.com", "ann@example.com"}

    await _sign_in(client, "ann@example.com")
    me = (await client.get(ME)).json()
    assert me["permissions"] == ["admin.access", "leads.export", "leads.read"]
    assert me["areas"] == ["admin", "user"]
    assert (await client.get(f"{ADMIN}/leads")).status_code == 200
    # Reading is open in the admin area, changing is not
    assert (await client.get(ROLES)).status_code == 200
    assert (await client.post(ROLES, json={"name": "Mine"})).status_code == 403

    await _sign_in(client, "root@example.com")
    response = await client.put(f"{GROUPS}/{group['id']}", json={"name": "HQ", "roles": ["export"]})
    assert (response.json()["name"], response.json()["roles"]) == ("HQ", ["export"])
    assert response.json()["users"] == 1
    assert (await client.delete(f"{GROUPS}/{group['id']}")).status_code == 204
    assert (await client.get(USERS, params={"q": "ann"})).json()["items"][0]["groups"] == []
    await _sign_in(client, "ann@example.com")
    assert (await client.get(ME)).json()["permissions"] == []


async def test_nobody_gives_more_than_they_have(auth_client):
    client, session_factory = await _root(auth_client)
    manager = ["admin.access", "users.read", "users.block", "users.roles", "roles.manage"]
    await client.post(ROLES, json={"name": "Manager", "permissions": manager})
    await client.post(ROLES, json={"name": "Helper", "permissions": ["admin.access"]})
    powerful = (await client.post(GROUPS, json={"name": "Staff", "roles": ["moderator"]})).json()
    for name, role in (("boss", "manager"), ("mod", "moderator"), ("ann", "user")):
        await create_user(session_factory, f"{name}@example.com", role)
    ann = await _id(session_factory, "ann@example.com")
    mod = await _id(session_factory, "mod@example.com")

    await _sign_in(client, "boss@example.com")
    not_allowed = (403, "permission_not_allowed")

    # Roles: only with permissions the manager has
    response = await client.post(ROLES, json={"name": "Leads", "permissions": ["leads.read"]})
    assert (response.status_code, response.json()["code"]) == not_allowed
    response = await client.put(f"{ROLES}/helper", json={"permissions": ["settings.mail"]})
    assert (response.status_code, response.json()["code"]) == not_allowed
    response = await client.put(f"{ROLES}/moderator", json={"permissions": []})
    assert (response.status_code, response.json()["code"]) == not_allowed
    response = await client.put(f"{ROLES}/helper", json={"permissions": ["users.read"]})
    assert response.status_code == 200

    # Groups: only with roles the manager covers
    response = await client.post(GROUPS, json={"name": "Mods", "roles": ["moderator"]})
    assert (response.status_code, response.json()["code"]) == not_allowed
    response = await client.delete(f"{GROUPS}/{powerful['id']}")
    assert (response.status_code, response.json()["code"]) == not_allowed
    helpers = (await client.post(GROUPS, json={"name": "Helpers", "roles": ["helper"]})).json()

    # Users: the same for what is given and for whom is managed
    response = await client.patch(f"{USERS}/{ann}", json={"role": "moderator"})
    assert (response.status_code, response.json()["code"]) == not_allowed
    response = await client.patch(f"{USERS}/{ann}", json={"groups": [powerful["id"]]})
    assert (response.status_code, response.json()["code"]) == not_allowed
    response = await client.patch(f"{USERS}/{mod}", json={"is_active": False})
    assert (response.status_code, response.json()["code"]) == not_allowed
    response = await client.patch(f"{USERS}/{ann}", json={"role": "root"})
    assert (response.status_code, response.json()["code"]) == (403, "role_protected")
    response = await client.patch(f"{USERS}/{ann}", json={"role": "nope"})
    assert (response.status_code, response.json()["code"]) == (400, "role_unknown")
    response = await client.patch(
        f"{USERS}/{ann}", json={"groups": ["00000000-0000-0000-0000-000000000000"]}
    )
    assert (response.status_code, response.json()["code"]) == (400, "group_unknown")

    response = await client.patch(
        f"{USERS}/{ann}", json={"role": "helper", "groups": [helpers["id"]]}
    )
    assert response.status_code == 200, response.text
    assert (response.json()["role"], response.json()["groups"]) == ("helper", [helpers["id"]])


async def test_moderator_does_not_block_a_user_in_a_group(auth_client):
    client, session_factory = await _root(auth_client)
    group = (await client.post(GROUPS, json={"name": "Staff", "roles": ["moderator"]})).json()
    await create_user(session_factory, "mod@example.com", "moderator")
    await create_user(session_factory, "ann@example.com", "user")
    ann = await _id(session_factory, "ann@example.com")
    await client.patch(f"{USERS}/{ann}", json={"groups": [group["id"]]})

    await _sign_in(client, "mod@example.com")
    response = await client.patch(f"{USERS}/{ann}", json={"is_active": False})
    assert response.status_code == 403


async def test_overview_counts_every_role(auth_client):
    client, session_factory = await _root(auth_client)
    await client.post(ROLES, json={"name": "Sales"})
    await create_user(session_factory, "ann@example.com", "sales")
    overview = (await client.get(f"{ADMIN}/overview")).json()
    assert overview["users_by_role"] == {"moderator": 0, "root": 1, "user": 0, "sales": 1}


async def test_the_sign_up_role_gets_no_staff_permissions(auth_client, monkeypatch):
    """Everyone gets `user` at sign-up: a person becomes staff with another role or a
    group, never by changing `user` for all of them."""
    client, session_factory = await _root(auth_client)
    await create_user(session_factory, "ann@example.com", "user")

    response = await client.put(f"{ROLES}/user", json={"permissions": ["admin.access"]})
    assert (response.status_code, response.json()["code"]) == (403, "role_user_staff")

    # Stored there before this rule (or by hand in the database): it does nothing
    async with session_factory() as session:
        await session.execute(
            update(RoleRecord)
            .where(RoleRecord.slug == "user")
            .values(permissions=["admin.access", "leads.read"])
        )
        await session.commit()
    async with session_factory() as session:
        readers = await users_with_permission(session, "leads.read")
    assert {user.email for user in readers} == {"root@example.com"}
    roles = {role["slug"]: role for role in (await client.get(ROLES)).json()}
    assert roles["user"]["permissions"] == []

    await _sign_in(client, "ann@example.com")
    me = (await client.get(ME)).json()
    assert (me["permissions"], me["areas"]) == ([], ["user"])
    assert (await client.get(f"{ADMIN}/overview")).status_code == 403

    # A permission of the user area may be given to everyone
    monkeypatch.setattr(permissions, "_declared", {*permissions._declared, "files.share"})
    monkeypatch.setattr(permissions, "_everyone", {"files.share"})
    await _sign_in(client, "root@example.com")
    listed = {item["name"]: item for item in (await client.get(f"{ADMIN}/permissions")).json()}
    assert listed["files.share"]["everyone"] is True
    assert listed["leads.read"]["everyone"] is False
    response = await client.put(f"{ROLES}/user", json={"permissions": ["files.share"]})
    assert response.status_code == 200, response.text
    assert response.json()["permissions"] == ["files.share"]


async def test_permissions_of_switched_off_modules_count(auth_client):
    """A role keeps the permissions of a module that is off; whoever gives the role
    must have them too, or it would hand them out once the module is on again."""
    client, session_factory = await _root(auth_client)
    manager = ["admin.access", "users.read", "users.roles", "roles.manage"]
    await client.post(ROLES, json={"name": "Manager", "permissions": manager})
    async with session_factory() as session:
        session.add(
            RoleRecord(slug="archive", name="Archive", permissions=["admin.access", "gone.read"])
        )
        await session.commit()
    await create_user(session_factory, "boss@example.com", "manager")
    await create_user(session_factory, "ann@example.com", "user")
    ann = await _id(session_factory, "ann@example.com")

    await _sign_in(client, "boss@example.com")
    not_allowed = (403, "permission_not_allowed")
    response = await client.patch(f"{USERS}/{ann}", json={"role": "archive"})
    assert (response.status_code, response.json()["code"]) == not_allowed
    response = await client.post(GROUPS, json={"name": "Old", "roles": ["archive"]})
    assert (response.status_code, response.json()["code"]) == not_allowed
    response = await client.put(f"{ROLES}/archive", json={"name": "Old archive"})
    assert (response.status_code, response.json()["code"]) == not_allowed

    # Root has every permission, also those
    await _sign_in(client, "root@example.com")
    response = await client.patch(f"{USERS}/{ann}", json={"role": "archive"})
    assert response.status_code == 200, response.text
    async with session_factory() as session:
        stored = await session.get(RoleRecord, "archive")
    assert stored.permissions == ["admin.access", "gone.read"]
