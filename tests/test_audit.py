"""Admin → Audit log: actions are recorded with the change and read with audit.read."""

import pytest
from sqlalchemy import select, text

from app.core.i18n import catalogs
from app.modules.admin.audit import SECRET, all_actions, diff
from app.modules.admin.models import AuditRecord
from app.modules.auth.models import User
from app.modules.leads.models import Lead
from tests.conftest import create_user, login

pytestmark = [pytest.mark.anyio, pytest.mark.modules("admin")]

ADMIN = "/api/v1/admin"
AUDIT = f"{ADMIN}/audit"


async def _root(auth_client):
    client, session_factory = auth_client
    await create_user(session_factory, "root@example.com", "root")
    await login(client, "root@example.com")
    return client, session_factory


async def _records(session_factory) -> list[AuditRecord]:
    async with session_factory() as session:
        return list(await session.scalars(select(AuditRecord).order_by(AuditRecord.created_at)))


async def _user_id(session_factory, email: str) -> str:
    async with session_factory() as session:
        return str(await session.scalar(select(User.id).where(User.email == email)))


def test_diff_keeps_changed_fields_and_hides_secrets():
    before = {"name": "A", "token": "old", "same": 1}
    after = {"name": "B", "token": "new", "same": 1, "added": True}
    assert diff(before, after, secret={"token"}) == {
        "added": [None, True],
        "name": ["A", "B"],
        "token": [SECRET, SECRET],
    }
    assert diff(before, before) == {}


async def test_every_action_has_texts(auth_client):
    # The admin modules are loaded with the app of auth_client
    assert {"users.block", "roles.create", "settings.update", "leads.delete"} <= all_actions()
    for language, catalog in catalogs.items():
        for name in all_actions():
            assert name in catalog["audit"], (language, name)


async def test_user_changes_are_recorded(auth_client):
    client, session_factory = await _root(auth_client)
    await create_user(session_factory, "ann@example.com", "user")
    ann = await _user_id(session_factory, "ann@example.com")
    group = (await client.post(f"{ADMIN}/groups", json={"name": "Team"})).json()

    await client.patch(f"{ADMIN}/users/{ann}", json={"is_active": False})
    await client.patch(f"{ADMIN}/users/{ann}", json={"role": "moderator", "groups": [group["id"]]})
    # Nothing changes: nothing recorded
    await client.patch(f"{ADMIN}/users/{ann}", json={"role": "moderator", "is_active": False})

    records = [record for record in await _records(session_factory) if record.target_id == ann]
    assert [record.action for record in records] == ["users.block", "users.access"]
    block, access = records
    assert (block.actor_email, block.target, block.changes) == (
        "root@example.com",
        "ann@example.com",
        None,
    )
    assert block.actor_id is not None
    assert access.changes == {"groups": [[], ["Team"]], "role": ["user", "moderator"]}


async def test_refused_change_leaves_no_record(auth_client):
    client, session_factory = await _root(auth_client)
    response = await client.post(f"{ADMIN}/roles", json={"name": "X", "permissions": ["nope"]})
    assert response.status_code == 400
    assert await _records(session_factory) == []


async def test_roles_and_groups_are_recorded(auth_client):
    client, session_factory = await _root(auth_client)
    role = (await client.post(f"{ADMIN}/roles", json={"name": "Sales"})).json()
    await client.put(f"{ADMIN}/roles/{role['slug']}", json={"permissions": ["leads.read"]})
    group = (await client.post(f"{ADMIN}/groups", json={"name": "Team"})).json()
    await client.put(f"{ADMIN}/groups/{group['id']}", json={"roles": ["sales"]})
    await client.delete(f"{ADMIN}/groups/{group['id']}")
    await client.delete(f"{ADMIN}/roles/sales")

    records = await _records(session_factory)
    assert [(r.action, r.target) for r in records] == [
        ("roles.create", "Sales"),
        ("roles.update", "Sales"),
        ("groups.create", "Team"),
        ("groups.update", "Team"),
        ("groups.delete", "Team"),
        ("roles.delete", "Sales"),
    ]
    assert records[0].changes == {"name": [None, "Sales"], "permissions": [None, []]}
    assert records[1].changes == {"permissions": [[], ["leads.read"]]}
    assert records[3].changes == {"roles": [[], ["sales"]]}
    assert records[2].target_id == group["id"]


async def test_settings_changes_are_recorded(auth_client):
    client, session_factory = await _root(auth_client)
    response = await client.put(f"{ADMIN}/settings/site", json={"name": "New"})
    assert response.status_code == 200, response.text
    # The same values again: no record
    await client.put(f"{ADMIN}/settings/site", json={"name": "New"})

    (record,) = await _records(session_factory)
    assert (record.action, record.target_id) == ("settings.update", "site")
    assert list(record.changes) == ["name"]
    assert record.changes["name"][1] == "New"


async def test_channel_secrets_are_not_recorded(auth_client):
    client, session_factory = await _root(auth_client)
    channel = {
        "type": "lead_telegram",
        "name": "Sales chat",
        "params": {"bot_token": "123:abc", "chat_id": "-100"},
    }
    created = (await client.post(f"{ADMIN}/entities", json=channel)).json()
    await client.put(
        f"{ADMIN}/entities/{created['id']}",
        json={"params": {"bot_token": "456:def", "chat_id": "-200"}},
    )
    await client.delete(f"{ADMIN}/entities/{created['id']}")

    create, update, delete = await _records(session_factory)
    assert create.action == "entities.create"
    assert create.changes["params.bot_token"] == [SECRET, SECRET]
    assert create.changes["params.chat_id"] == [None, "-100"]
    assert update.changes == {
        "params.bot_token": [SECRET, SECRET],
        "params.chat_id": ["-100", "-200"],
    }
    assert (delete.action, delete.target) == ("entities.delete", "Sales chat")
    assert "123:abc" not in str([create.changes, update.changes])


async def test_leads_and_exports_are_recorded(auth_client):
    client, session_factory = await _root(auth_client)
    async with session_factory() as session:
        lead = Lead(form="contact", data={"email": "visitor@example.com"}, language="en")
        session.add(lead)
        await session.commit()
        lead_id = str(lead.id)

    await client.patch(f"{ADMIN}/leads/{lead_id}", json={"status": "done"})
    assert (await client.get(f"{ADMIN}/leads/export", params={"status": "done"})).status_code == 200
    assert (await client.get(f"{ADMIN}/users/export", params={"q": " ann "})).status_code == 200
    await client.delete(f"{ADMIN}/leads/{lead_id}")

    records = await _records(session_factory)
    assert [(r.action, r.changes) for r in records] == [
        ("leads.update", {"status": ["new", "done"]}),
        ("leads.export", {"status": "done"}),
        ("users.export", {"q": "ann"}),
        ("leads.delete", None),
    ]
    # The form, not what the visitor sent
    assert records[0].target == "contact"
    assert "visitor@example.com" not in str([r.changes for r in records])


async def test_log_is_read_with_filters(auth_client):
    client, session_factory = await _root(auth_client)
    await client.post(f"{ADMIN}/roles", json={"name": "Sales"})
    await client.post(f"{ADMIN}/groups", json={"name": "Team"})

    response = await client.get(AUDIT, headers={"Accept-Language": "ru"})
    assert response.status_code == 200, response.text
    page = response.json()
    assert page["total"] == 2
    newest = page["items"][0]
    assert (newest["action"], newest["title"], newest["target"]) == (
        "groups.create",
        "Создана группа",
        "Team",
    )
    assert newest["actor_email"] == "root@example.com"

    by_action = (await client.get(AUDIT, params={"action": "roles.create"})).json()
    assert [item["target"] for item in by_action["items"]] == ["Sales"]
    assert (await client.get(AUDIT, params={"q": "tea"})).json()["total"] == 1
    root = await _user_id(session_factory, "root@example.com")
    assert (await client.get(AUDIT, params={"actor": root})).json()["total"] == 2
    assert (await client.get(AUDIT, params={"since": "2999-01-01"})).json()["total"] == 0
    assert (await client.get(AUDIT, params={"until": "2000-01-01"})).json()["total"] == 0
    oldest = (await client.get(AUDIT, params={"sort": "created_at", "size": 1})).json()
    assert oldest["items"][0]["action"] == "roles.create"

    listed = (await client.get(f"{AUDIT}/actions")).json()
    actions = {item["name"]: item["title"] for item in listed}
    assert actions["roles.create"] == "Role created"


async def test_log_needs_audit_read(auth_client):
    client, session_factory = auth_client
    await create_user(session_factory, "moderator@example.com", "moderator")
    await login(client, "moderator@example.com")
    assert (await client.get(AUDIT)).status_code == 403
    assert (await client.get(f"{AUDIT}/actions")).status_code == 403


async def test_record_keeps_the_email_when_the_account_is_gone(auth_client):
    client, session_factory = await _root(auth_client)
    await client.post(f"{ADMIN}/roles", json={"name": "Sales"})
    async with session_factory() as session:
        # SQLite checks foreign keys (ON DELETE SET NULL) only when asked
        await session.execute(text("PRAGMA foreign_keys=ON"))
        root = await session.scalar(select(User).where(User.email == "root@example.com"))
        await session.delete(root)
        await session.commit()

    (record,) = await _records(session_factory)
    assert (record.actor_id, record.actor_email) == (None, "root@example.com")
