import pytest


@pytest.mark.anyio
async def test_health(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_bootstrap(client):
    response = await client.get("/api/v1/bootstrap")
    assert response.status_code == 200
    data = response.json()
    assert data["profile"] == "standard"
    assert data["features"]["authentication"] is True
