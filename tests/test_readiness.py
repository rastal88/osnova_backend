import asyncio

import pytest

from app.core import readiness


@pytest.mark.anyio
async def test_ready_checks_the_database(client):
    response = await client.get("/api/v1/ready")
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ok", "checks": {"database": True}}


@pytest.mark.anyio
async def test_a_failing_or_hanging_dependency_gives_503(client, monkeypatch):
    async def down():
        raise ConnectionError("database is down")

    async def hangs():
        await asyncio.sleep(10)

    monkeypatch.setattr(readiness, "TIMEOUT_SECONDS", 0.1)
    monkeypatch.setitem(readiness.checks, "database", down)
    monkeypatch.setitem(readiness.checks, "redis", hangs)

    response = await client.get("/api/v1/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "checks": {"database": False, "redis": False},
    }
    # Liveness does not depend on them
    assert (await client.get("/api/v1/health")).status_code == 200


@pytest.mark.anyio
async def test_cors_preflight_still_works(client):
    response = await client.options(
        "/api/v1/forms/contact",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-credentials"] == "true"
