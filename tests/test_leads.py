import pytest
from sqlalchemy import func, select

from app.modules.leads.models import Lead
from tests.conftest import create_user, login

LEADS = "/api/v1/admin/leads"
CONTACT = {
    "name": "Ann",
    "email": "ann@example.com",
    "message": "Please call me back tomorrow",
    "consent": True,
}


async def _submit(client, **changes):
    response = await client.post("/api/v1/forms/contact", json={**CONTACT, **changes})
    assert response.status_code == 200, response.text


async def _count(session_factory) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count()).select_from(Lead))


async def _admin(auth_client, role="moderator"):
    client, session_factory = auth_client
    await create_user(session_factory, f"{role}@example.com", role)
    await login(client, f"{role}@example.com")
    return client, session_factory


@pytest.mark.anyio
async def test_submission_is_stored_once(auth_client):
    client, session_factory = auth_client
    await _submit(client)
    assert await _count(session_factory) == 1

    # Invalid and honeypot submissions are not stored
    await client.post("/api/v1/forms/contact", json={**CONTACT, "email": "bad"})
    await client.post("/api/v1/forms/contact", json={**CONTACT, "website": "spam"})
    assert await _count(session_factory) == 1


@pytest.mark.anyio
async def test_admin_lists_searches_and_filters(auth_client):
    client, _ = await _admin(auth_client)
    await _submit(client, name="Ann")
    await _submit(client, name="Bob", email="bob@example.com")

    response = await client.get(LEADS)
    assert response.status_code == 200, response.text
    page = response.json()
    assert page["total"] == 2
    # Newest first
    assert [item["data"]["name"] for item in page["items"]] == ["Bob", "Ann"]
    assert page["items"][0]["status"] == "new"
    assert page["items"][0]["form"] == "contact"

    response = await client.get(LEADS, params={"q": "BOB@"})
    assert [item["data"]["name"] for item in response.json()["items"]] == ["Bob"]

    response = await client.get(LEADS, params={"status": "done"})
    assert response.json()["total"] == 0
    response = await client.get(LEADS, params={"form": "contact,unknown"})
    assert response.json()["total"] == 2


@pytest.mark.anyio
async def test_mark_done_and_delete(auth_client):
    client, session_factory = await _admin(auth_client)
    await _submit(client)
    lead = (await client.get(LEADS)).json()["items"][0]

    response = await client.patch(f"{LEADS}/{lead['id']}", json={"status": "done"})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "done"
    assert (await client.patch(f"{LEADS}/{lead['id']}", json={"status": "x"})).status_code == 422

    assert (await client.delete(f"{LEADS}/{lead['id']}")).status_code == 204
    assert await _count(session_factory) == 0
    assert (await client.delete(f"{LEADS}/{lead['id']}")).status_code == 404


@pytest.mark.anyio
async def test_forms_for_the_admin(auth_client):
    client, _ = await _admin(auth_client)
    response = await client.get(f"{LEADS}/forms", headers={"Accept-Language": "ru"})
    assert response.status_code == 200
    (contact,) = response.json()
    assert contact["name"] == "contact"
    assert contact["fields"][0]["label"] == "Имя"


@pytest.mark.anyio
async def test_only_admins_see_leads(auth_client):
    client, session_factory = auth_client
    assert (await client.get(LEADS)).status_code == 401
    await create_user(session_factory, "user@example.com", "user")
    await login(client, "user@example.com")
    assert (await client.get(LEADS)).status_code == 403


@pytest.mark.anyio
async def test_stats_for_the_overview(auth_client):
    from datetime import UTC, datetime, timedelta

    client, session_factory = await _admin(auth_client)
    now = datetime.now(UTC).replace(tzinfo=None)
    async with session_factory() as session:
        for days_ago, status in ((0, "new"), (0, "done"), (2, "new"), (30, "done")):
            lead = Lead(form="contact", data={}, language="en", status=status)
            lead.created_at = now - timedelta(days=days_ago)
            session.add(lead)
        await session.commit()

    response = await client.get(f"{LEADS}/stats", params={"days": 7})
    assert response.status_code == 200, response.text
    stats = response.json()
    assert stats["total"] == 4
    assert stats["by_status"] == {"new": 2, "done": 2}
    by_day = stats["by_day"]
    assert len(by_day) == 7
    assert by_day[-1] == {"date": now.date().isoformat(), "count": 2}
    assert by_day[-3]["count"] == 1
    # The lead of 30 days ago is outside the period
    assert sum(day["count"] for day in by_day) == 3

    assert (await client.get(f"{LEADS}/stats", params={"days": 0})).status_code == 422
