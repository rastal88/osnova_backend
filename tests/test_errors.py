import re

import pytest
from httpx import ASGITransport, AsyncClient

from app import create_app
from app.core.i18n import catalogs, resolve_language
from app.core.languages import AVAILABLE_LANGUAGES
from tests.conftest import login, register

RU = {"Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8"}


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, "en"),
        ("", "en"),
        ("ru", "ru"),
        ("ru-RU,ru;q=0.9", "ru"),
        ("de, en;q=0.5, ru;q=0.8", "ru"),
        ("ru;q=0, en", "en"),
        ("de-DE", "en"),
        ("ru;q=bad, en", "en"),
    ],
)
def test_resolve_language(header, expected):
    assert resolve_language(header) == expected


def test_catalogs_have_same_keys_and_placeholders():
    placeholders = re.compile(r"{(\w+)}")
    reference = catalogs["en"]
    for code in AVAILABLE_LANGUAGES:
        catalog = catalogs[code]
        assert catalog.keys() == reference.keys(), code
        for section, messages in reference.items():
            assert catalog[section].keys() == messages.keys(), (code, section)
            for key, message in messages.items():
                expected = set(placeholders.findall(message))
                assert set(placeholders.findall(catalog[section][key])) == expected, key


@pytest.mark.anyio
async def test_not_found_in_request_language(client):
    response = await client.get("/api/v1/missing")
    assert response.status_code == 404
    assert response.json() == {"code": "not_found", "message": "Not found."}
    assert response.headers["content-language"] == "en"

    response = await client.get("/api/v1/missing", headers=RU)
    assert response.json() == {"code": "not_found", "message": "Не найдено."}
    assert response.headers["content-language"] == "ru"
    assert "Accept-Language" in response.headers["vary"]


@pytest.mark.anyio
async def test_validation_error_lists_fields(auth_client):
    client, _ = auth_client
    response = await client.post("/api/v1/auth/register", json={"email": "a@b.com"}, headers=RU)
    assert response.status_code == 422
    assert response.json() == {
        "code": "validation_error",
        "message": "Проверьте выделенные поля.",
        "fields": [{"field": "password", "code": "missing", "message": "Обязательное поле."}],
    }


@pytest.mark.anyio
async def test_auth_errors_use_codes(auth_client):
    client, _ = auth_client

    response = await register(client, "short@example.com", "short")
    assert response.status_code == 422
    assert response.json()["fields"] == [
        {
            "field": "password",
            "code": "string_too_short",
            "message": "Must be at least 8 characters.",
        }
    ]

    response = await register(client, "mail@example.com", "mail@example.com1")
    assert response.status_code == 400
    assert response.json()["code"] == "password_contains_email"

    await register(client, "user@example.com")
    response = await register(client, "user@example.com")
    assert response.json()["code"] == "register_user_already_exists"

    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "user@example.com", "password": "wrong-password"},
        headers=RU,
    )
    assert response.status_code == 400
    assert response.json() == {
        "code": "login_bad_credentials",
        "message": "Неверный email или пароль.",
    }

    await login(client, "user@example.com")
    response = await client.get("/api/v1/file_flow/download/missing.txt")
    assert response.status_code == 404
    assert response.json()["code"] == "file_not_found"


@pytest.mark.anyio
async def test_unhandled_error_is_hidden():
    app = create_app()

    @app.get("/boom")
    async def boom():
        raise RuntimeError("secret details")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/boom", headers=RU)

    assert response.status_code == 500
    assert response.json() == {
        "code": "internal_error",
        "message": "Что-то пошло не так. Попробуйте позже.",
        "request_id": response.headers["X-Request-ID"],
    }
