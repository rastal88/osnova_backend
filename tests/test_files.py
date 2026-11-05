import pytest

from tests.conftest import login, register


@pytest.mark.anyio
async def test_upload_requires_auth(auth_client):
    client, _ = auth_client
    files = {"file": ("test.txt", b"hello", "text/plain")}
    response = await client.post("/api/v1/file_flow/upload", files=files)
    assert response.status_code == 401


@pytest.mark.anyio
async def test_upload_and_download(auth_client):
    client, _ = auth_client
    await register(client, "user@example.com")
    await login(client, "user@example.com")

    files = {"file": ("../../evil name.TXT", b"hello world", "text/plain")}
    response = await client.post("/api/v1/file_flow/upload", files=files)
    assert response.status_code == 200, response.text
    data = response.json()
    assert "/" not in data["stored_name"]
    assert data["stored_name"].endswith(".txt")

    download = await client.get(data["url"])
    assert download.status_code == 200
    assert download.content == b"hello world"


@pytest.mark.anyio
@pytest.mark.parametrize("name", ["..%2F..%2Fapp%2Fconfig.py", "config.py", "%2e%2e"])
async def test_download_rejects_unknown_names(auth_client, name):
    client, _ = auth_client
    response = await client.get(f"/api/v1/file_flow/download/{name}")
    assert response.status_code == 404
