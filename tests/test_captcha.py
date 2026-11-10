import logging

import pytest

from app.config import config
from app.core import captcha
from tests.conftest import create_user, login

FORM = "/api/v1/forms/contact"
REGISTER = "/api/v1/auth/register"
SETTINGS = "/api/v1/admin/settings"
CONTACT = {
    "name": "Ann",
    "email": "ann@example.com",
    "message": "Please call me back tomorrow",
    "consent": True,
}
GOOD = {captcha.HEADER: "good-token"}


@pytest.fixture
def turnstile(monkeypatch):
    """Captcha configured; the provider accepts "good-token". Returns the calls it got."""
    calls: list[tuple[str, str]] = []

    def verify(secret: str, token: str) -> bool:
        calls.append((secret, token))
        if token == "outage":
            raise TimeoutError("no answer")
        return token == "good-token"

    monkeypatch.setattr(config, "CAPTCHA_PROVIDER", "turnstile")
    monkeypatch.setattr(config, "CAPTCHA_SITE_KEY", "site-key")
    monkeypatch.setattr(config, "CAPTCHA_SECRET_KEY", "secret-key")
    monkeypatch.setitem(captcha.PROVIDERS, "turnstile", verify)
    return calls


@pytest.mark.anyio
async def test_off_by_default(client):
    assert (await client.get("/api/v1/bootstrap")).json()["captcha"] is None
    assert (await client.post(FORM, json=CONTACT)).status_code == 200


@pytest.mark.anyio
async def test_form_needs_an_accepted_token(client, turnstile):
    bootstrap = (await client.get("/api/v1/bootstrap")).json()
    assert bootstrap["captcha"] == {"provider": "turnstile", "site_key": "site-key"}

    response = await client.post(FORM, json=CONTACT, headers={"Accept-Language": "ru"})
    assert response.status_code == 400
    assert response.json()["code"] == "captcha_failed"
    assert "робот" in response.json()["message"]
    assert turnstile == []  # nothing to ask the provider about

    response = await client.post(FORM, json=CONTACT, headers={captcha.HEADER: "bad-token"})
    assert response.status_code == 400

    response = await client.post(FORM, json=CONTACT, headers=GOOD)
    assert response.status_code == 200, response.text
    assert turnstile == [("secret-key", "bad-token"), ("secret-key", "good-token")]


@pytest.mark.anyio
async def test_token_is_not_used_up_by_invalid_fields_or_bots(client, turnstile):
    response = await client.post(FORM, json={**CONTACT, "email": "bad"}, headers=GOOD)
    assert response.status_code == 422
    response = await client.post(FORM, json={**CONTACT, "website": "spam"})
    assert response.status_code == 200  # honeypot: dropped silently
    assert turnstile == []


@pytest.mark.anyio
async def test_provider_outage_lets_requests_through(client, turnstile, caplog):
    with caplog.at_level(logging.WARNING, logger="app.core.captcha"):
        response = await client.post(FORM, json=CONTACT, headers={captcha.HEADER: "outage"})
    assert response.status_code == 200, response.text
    assert "unreachable" in caplog.text


@pytest.mark.anyio
async def test_sign_up_needs_a_token_and_sign_in_does_not(auth_client, turnstile):
    client, session_factory = auth_client
    user = {"email": "new@example.com", "password": "password123"}

    assert (await client.post(REGISTER, json=user)).status_code == 400
    assert (await client.post(REGISTER, json=user, headers=GOOD)).status_code == 201

    await create_user(session_factory, "old@example.com", "user")
    assert (await login(client, "old@example.com")).status_code == 204


@pytest.mark.anyio
async def test_root_switches_it_off_and_on_in_the_admin(auth_client, turnstile):
    client, session_factory = auth_client
    await create_user(session_factory, "root@example.com", "root")
    await login(client, "root@example.com")

    groups = {group["name"]: group for group in (await client.get(SETTINGS)).json()}
    assert groups["protection"]["title"] == "Protection"
    assert groups["protection"]["values"] == {"captcha": True}
    assert groups["protection"]["fields"][0]["type"] == "checkbox"

    response = await client.put(f"{SETTINGS}/protection", json={"captcha": False})
    assert response.status_code == 200, response.text
    assert (await client.get("/api/v1/bootstrap")).json()["captcha"] is None
    assert (await client.post(FORM, json=CONTACT)).status_code == 200

    response = await client.put(f"{SETTINGS}/protection", json={"captcha": True})
    assert response.status_code == 200, response.text
    assert (await client.post(FORM, json=CONTACT)).status_code == 400


@pytest.mark.anyio
async def test_switching_on_without_keys_says_so(auth_client, monkeypatch):
    client, session_factory = auth_client
    await create_user(session_factory, "root@example.com", "root")
    await login(client, "root@example.com")
    monkeypatch.setattr(config, "CAPTCHA_PROVIDER", "turnstile")  # no keys

    assert (await client.get("/api/v1/bootstrap")).json()["captcha"] is None
    response = await client.put(
        f"{SETTINGS}/protection", json={"captcha": True}, headers={"Accept-Language": "ru"}
    )
    assert response.status_code == 422, response.text
    (field,) = response.json()["fields"]
    assert field["field"] == "captcha"
    assert field["code"] == "captcha_not_configured"
    assert "CAPTCHA_SECRET_KEY" in field["message"]

    # Switching it off is always allowed
    response = await client.put(f"{SETTINGS}/protection", json={"captcha": False})
    assert response.status_code == 200, response.text


def test_turnstile_request_and_answers(monkeypatch):
    sent = []

    class Answer:
        def __init__(self, body: bytes):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, *args):
            return self.body

    def fake_urlopen(url, data, timeout):
        sent.append((url, data.decode(), timeout))
        ok = b"response=good" in data
        return Answer(b'{"success": true}' if ok else b'{"success": false, "error-codes": ["x"]}')

    monkeypatch.setattr(captcha.urllib.request, "urlopen", fake_urlopen)
    assert captcha._turnstile("s3cret", "good") is True
    assert captcha._turnstile("s3cret", "bad") is False
    url, body, timeout = sent[0]
    assert url == "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    # Only the secret and the token: no visitor IP
    assert body == "secret=s3cret&response=good"
    assert timeout == captcha.TIMEOUT


def test_provider_without_keys_warns_at_start(monkeypatch, caplog):
    monkeypatch.setattr(config, "CAPTCHA_PROVIDER", "turnstile")
    with caplog.at_level(logging.WARNING, logger="app.core.captcha"):
        captcha.check_captcha_config()
    assert "the captcha is off" in caplog.text
