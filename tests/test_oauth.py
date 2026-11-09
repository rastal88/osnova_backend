from urllib.parse import parse_qs, urlparse

import pytest
from httpx_oauth.clients.google import GoogleOAuth2
from sqlalchemy import select

from app.config import Settings, config
from app.core.capabilities import oauth_providers
from app.modules.auth.models import OAuthAccount
from tests.conftest import create_user, login

GOOGLE = "/api/v1/auth/google"


@pytest.fixture
def google(monkeypatch):
    """Google's answers: the code is exchanged for a token, the token gives the account."""
    account = {"id": "google-123", "email": "ann@gmail.com"}

    async def get_access_token(self, code, redirect_uri, code_verifier=None):
        assert code == "good-code"
        return {"access_token": "token", "expires_at": 2_000_000_000}

    async def get_id_email(self, token):
        return account["id"], account["email"]

    monkeypatch.setattr(GoogleOAuth2, "get_access_token", get_access_token)
    monkeypatch.setattr(GoogleOAuth2, "get_id_email", get_id_email)
    return account


async def _authorize(client) -> str:
    response = await client.get(f"{GOOGLE}/authorize")
    assert response.status_code == 200, response.text
    url = urlparse(response.json()["authorization_url"])
    query = parse_qs(url.query)
    assert url.netloc == "accounts.google.com"
    assert query["client_id"] == ["test-client-id"]
    assert query["redirect_uri"] == [f"{config.FRONTEND_URL}/oauth/google/callback"]
    return query["state"][0]


def test_providers_need_both_keys():
    def providers(auth=True, client_id="id", secret="s"):
        values = {"AUTH_ENABLED": auth, "GOOGLE_CLIENT_ID": client_id}
        return oauth_providers(Settings(_env_file=None, **values, GOOGLE_CLIENT_SECRET=secret))

    assert providers() == ["google"]
    assert providers(secret=None) == []
    assert providers(client_id=None) == []
    assert providers(auth=False) == []


@pytest.mark.anyio
async def test_bootstrap_lists_providers(client):
    assert (await client.get("/api/v1/bootstrap")).json()["auth_providers"] == ["google"]


@pytest.mark.anyio
async def test_new_user_signs_up_with_google(auth_client, google):
    client, _ = auth_client
    state = await _authorize(client)

    response = await client.get(f"{GOOGLE}/callback", params={"code": "good-code", "state": state})
    assert response.status_code == 204, response.text

    me = (await client.get("/api/v1/auth/users/me")).json()
    assert me["email"] == "ann@gmail.com"
    assert me["is_verified"] is True
    assert me["role"] == "user"


@pytest.mark.anyio
async def test_existing_account_is_linked_by_email(auth_client, google):
    client, session_factory = auth_client
    await create_user(session_factory, "ann@gmail.com", "moderator")

    state = await _authorize(client)
    await client.get(f"{GOOGLE}/callback", params={"code": "good-code", "state": state})

    me = (await client.get("/api/v1/auth/users/me")).json()
    assert me["role"] == "moderator"
    async with session_factory() as session:
        account = await session.scalar(select(OAuthAccount))
    assert (account.oauth_name, account.account_id) == ("google", "google-123")

    # Signing in again finds the linked account
    await client.post("/api/v1/auth/logout")
    state = await _authorize(client)
    response = await client.get(f"{GOOGLE}/callback", params={"code": "good-code", "state": state})
    assert response.status_code == 204
    # The password still works too
    assert (await login(client, "ann@gmail.com")).status_code == 204


@pytest.mark.anyio
async def test_state_must_match_this_browser(auth_client, google):
    client, _ = auth_client
    state = await _authorize(client)
    # Another browser: no CSRF cookie from the authorize step
    client.cookies.clear()
    response = await client.get(f"{GOOGLE}/callback", params={"code": "good-code", "state": state})
    assert response.status_code == 400
    assert response.json()["code"] == "oauth_invalid_state"

    response = await client.get(f"{GOOGLE}/callback", params={"code": "good-code", "state": "x"})
    assert response.json()["code"] == "access_token_decode_error"


@pytest.mark.anyio
async def test_blocked_user_cannot_sign_in_with_google(auth_client, google):
    client, session_factory = auth_client
    await create_user(session_factory, "ann@gmail.com", "user")
    from app.modules.auth.models import User

    async with session_factory() as session:
        user = await session.scalar(select(User))
        user.is_active = False
        await session.commit()

    state = await _authorize(client)
    response = await client.get(f"{GOOGLE}/callback", params={"code": "good-code", "state": state})
    assert response.status_code == 400
    assert response.json()["code"] == "login_bad_credentials"
