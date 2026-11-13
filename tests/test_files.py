import io

import pytest
from fastapi import UploadFile

from app.core.settings import settings
from app.modules.files import routes as file_routes
from app.modules.files.settings import FilesSettings
from tests.conftest import create_user, login

pytestmark = pytest.mark.modules("files")

FILES = "/api/v1/files"


async def _user(auth_client, email="user@example.com", role="user"):
    client, session_factory = auth_client
    await create_user(session_factory, email, role)
    await login(client, email)
    return client, session_factory


async def _upload(client, name="notes.txt", body=b"hello world", content_type="text/plain"):
    response = await client.post(FILES, files={"file": (name, body, content_type)})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.anyio
async def test_files_require_sign_in(auth_client):
    client, _ = auth_client
    response = await client.post(FILES, files={"file": ("a.txt", b"x", "text/plain")})
    assert response.status_code == 401
    assert (await client.get(FILES)).status_code == 401


@pytest.mark.anyio
async def test_upload_list_download_delete(auth_client):
    client, _ = await _user(auth_client)

    uploaded = await _upload(client, name="../../Отчёт 2026.TXT")
    assert uploaded["name"] == "Отчёт 2026.TXT"
    assert uploaded["size"] == 11
    assert uploaded["url"] == f"{FILES}/{uploaded['id']}"

    listed = (await client.get(FILES)).json()
    assert listed["total"] == 1
    assert listed["items"][0]["id"] == uploaded["id"]
    # SQLite compares Cyrillic case-sensitively; PostgreSQL ILIKE does not
    assert (await client.get(FILES, params={"q": "Отчёт"})).json()["total"] == 1

    download = await client.get(uploaded["url"])
    assert download.status_code == 200
    assert download.content == b"hello world"
    # Not an image: always a download, never rendered by the browser
    assert download.headers["content-type"] == "application/octet-stream"
    assert download.headers["content-disposition"].startswith("attachment;")
    disposition = download.headers["content-disposition"]
    assert "filename*=UTF-8''%D0%9E%D1%82%D1%87%D1%91%D1%82" in disposition

    assert download.headers["x-content-type-options"] == "nosniff"

    assert (await client.delete(uploaded["url"])).status_code == 204
    assert (await client.get(uploaded["url"])).status_code == 404
    assert (await client.get(FILES)).json()["total"] == 0


@pytest.mark.anyio
async def test_html_is_never_served_as_a_page(auth_client):
    client, _ = await _user(auth_client)
    uploaded = await _upload(client, "x.html", b"<script>alert(1)</script>", "text/html")
    download = await client.get(uploaded["url"])
    assert download.headers["content-type"] == "application/octet-stream"
    assert download.headers["content-disposition"].startswith("attachment;")

    image = await _upload(client, "pic.png", b"\x89PNG", "image/png")
    download = await client.get(image["url"])
    assert download.headers["content-type"] == "image/png"
    assert download.headers["content-disposition"].startswith("inline;")


@pytest.mark.anyio
async def test_only_owner_and_admins_reach_a_file(auth_client):
    client, session_factory = await _user(auth_client, "owner@example.com")
    uploaded = await _upload(client)

    await create_user(session_factory, "other@example.com", "user")
    await login(client, "other@example.com")
    assert (await client.get(uploaded["url"])).status_code == 404
    assert (await client.delete(uploaded["url"])).status_code == 404
    assert (await client.get(FILES)).json()["total"] == 0

    await create_user(session_factory, "mod@example.com", "moderator")
    await login(client, "mod@example.com")
    assert (await client.get(uploaded["url"])).status_code == 200


@pytest.mark.anyio
async def test_size_and_type_limits(auth_client):
    client, _ = await _user(auth_client)

    # Admin → Settings → Files
    settings.set(FilesSettings(max_size_mb=1))
    big = b"x" * (1024 * 1024 + 1)
    response = await client.post(FILES, files={"file": ("a.txt", big, "text/plain")})
    assert response.status_code == 413
    assert response.json()["code"] == "file_too_large"

    settings.set(FilesSettings(allowed_types="image/, application/pdf"))
    response = await client.post(FILES, files={"file": ("a.txt", b"1", "text/plain")})
    assert response.status_code == 415
    assert response.json()["code"] == "file_type_not_allowed"
    await _upload(client, "a.pdf", b"%PDF", "application/pdf")


@pytest.mark.anyio
async def test_odd_names_and_types_are_cleaned(auth_client):
    client, _ = await _user(auth_client)
    uploaded = await _upload(client, "C:\\temp\\ab.txt", b"x", "Text/Plain; charset=utf-8")
    assert uploaded["name"] == "ab.txt"
    assert uploaded["content_type"] == "text/plain"
    weird = await _upload(client, " ", b"x", "not a type")
    assert weird["name"] == "file"
    assert weird["content_type"] == "application/octet-stream"


def test_control_characters_are_removed_from_names():
    upload = UploadFile(file=io.BytesIO(), filename="a\x00b\x1f.txt")
    assert file_routes._name(upload) == "ab.txt"


def test_quoted_name_cannot_be_broken():
    from app.modules.files.storage import content_disposition

    value = content_disposition('a"b\\c.txt', inline=False)
    assert value.startswith('attachment; filename="abc.txt"; ')
