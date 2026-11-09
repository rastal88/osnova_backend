import pytest
from sqlalchemy import select

from app.modules.entities.models import Entity
from tests.conftest import create_user, login

ENTITIES = "/api/v1/admin/entities"
TELEGRAM = {
    "type": "lead_telegram",
    "name": "Sales chat",
    "params": {"bot_token": "123:abc", "chat_id": "-100"},
}


async def _signed_in(auth_client, role="root"):
    client, session_factory = auth_client
    await create_user(session_factory, f"{role}@example.com", role)
    await login(client, f"{role}@example.com")
    return client, session_factory


async def _stored_params(session_factory) -> dict:
    async with session_factory() as session:
        return (await session.scalar(select(Entity))).params


@pytest.mark.anyio
async def test_types_are_described(auth_client):
    client, _ = await _signed_in(auth_client, "moderator")
    response = await client.get(f"{ENTITIES}/types", params={"group": "lead_channels"})
    assert response.status_code == 200, response.text
    types = {item["type"]: item for item in response.json()}
    assert set(types) == {"lead_email", "lead_telegram", "lead_webhook"}
    token = types["lead_telegram"]["fields"][0]
    assert (token["name"], token["type"], token["required"]) == ("bot_token", "password", True)
    assert types["lead_telegram"]["title"] == "Telegram"


@pytest.mark.anyio
async def test_moderator_reads_only(auth_client):
    client, _ = await _signed_in(auth_client, "moderator")
    assert (await client.get(ENTITIES)).status_code == 200
    assert (await client.post(ENTITIES, json=TELEGRAM)).status_code == 403


@pytest.mark.anyio
async def test_secrets_are_masked_and_kept(auth_client):
    client, session_factory = await _signed_in(auth_client)

    response = await client.post(ENTITIES, json=TELEGRAM)
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["params"] == {"bot_token": "********", "chat_id": "-100"}
    assert created["enabled"] is True

    # The mask sent back keeps the stored token
    response = await client.put(
        f"{ENTITIES}/{created['id']}",
        json={"params": {"bot_token": "********", "chat_id": "-200"}, "enabled": False},
    )
    assert response.status_code == 200, response.text
    assert await _stored_params(session_factory) == {"bot_token": "123:abc", "chat_id": "-200"}

    new_token = {"params": {"bot_token": "9:z", "chat_id": "1"}}
    await client.put(f"{ENTITIES}/{created['id']}", json=new_token)
    assert (await _stored_params(session_factory))["bot_token"] == "9:z"

    listed = (await client.get(ENTITIES, params={"group": "lead_channels"})).json()
    assert [item["params"]["bot_token"] for item in listed] == ["********"]

    assert (await client.delete(f"{ENTITIES}/{created['id']}")).status_code == 204
    assert (await client.get(ENTITIES)).json() == []


@pytest.mark.anyio
async def test_invalid_params_return_field_errors(auth_client):
    client, _ = await _signed_in(auth_client)

    response = await client.post(
        ENTITIES, json={"type": "lead_telegram", "name": "x", "params": {"bot_token": "1"}}
    )
    assert response.status_code == 422
    assert [item["field"] for item in response.json()["fields"]] == ["params.chat_id"]

    response = await client.post(
        ENTITIES, json={"type": "lead_webhook", "name": "x", "params": {"url": "ftp://x"}}
    )
    assert response.json()["fields"][0]["field"] == "params.url"

    response = await client.post(ENTITIES, json={"type": "nope", "name": "x"})
    assert response.status_code == 404
