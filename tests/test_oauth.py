from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from httpx_oauth.exceptions import GetIdEmailError
from sqlalchemy import select

from app.config import Settings, config
from app.core.capabilities import oauth_providers
from app.modules.auth.models import OAuthAccount, User
from app.modules.auth.oauth import GoogleOpenID
from tests.conftest import create_user, login

pytestmark = pytest.mark.modules("auth")

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

    monkeypatch.setattr(GoogleOpenID, "get_access_token", get_access_token)
    monkeypatch.setattr(GoogleOpenID, "get_id_email", get_id_email)
    return account


async def _set_user(session_factory, **values):
    async with session_factory() as session:
        user = await session.scalar(select(User))
        for name, value in values.items():
            setattr(user, name, value)
        await session.commit()


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
    await _set_user(session_factory, is_verified=True)

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
    await _set_user(session_factory, is_active=False)

    state = await _authorize(client)
    response = await client.get(f"{GOOGLE}/callback", params={"code": "good-code", "state": state})
    assert response.status_code == 400
    assert response.json()["code"] == "login_bad_credentials"


@pytest.mark.anyio
async def test_unconfirmed_account_is_taken_over(auth_client, google):
    """Someone registered Ann's email without owning it: Google proves Ann owns it,
    so the password typed at sign-up stops working."""
    client, session_factory = auth_client
    await create_user(session_factory, "ann@gmail.com", "user")

    state = await _authorize(client)
    response = await client.get(f"{GOOGLE}/callback", params={"code": "good-code", "state": state})
    assert response.status_code == 204, response.text
    me = (await client.get("/api/v1/auth/users/me")).json()
    assert me["is_verified"] is True

    await client.post("/api/v1/auth/logout")
    assert (await login(client, "ann@gmail.com")).status_code == 400


@pytest.mark.anyio
async def test_provider_error_is_not_a_500(auth_client, google, monkeypatch):
    async def get_id_email(self, token):
        raise GetIdEmailError()

    monkeypatch.setattr(GoogleOpenID, "get_id_email", get_id_email)
    client, _ = auth_client
    state = await _authorize(client)
    response = await client.get(f"{GOOGLE}/callback", params={"code": "good-code", "state": state})
    assert response.status_code == 400
    assert response.json()["code"] == "oauth_provider_error"


def _userinfo(monkeypatch, status: int, body: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://openidconnect.googleapis.com/v1/userinfo"
        assert request.headers["Authorization"] == "Bearer token"
        return httpx.Response(status, json=body)

    monkeypatch.setattr(
        GoogleOpenID,
        "get_httpx_client",
        lambda self: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    return GoogleOpenID("id", "secret")


@pytest.mark.anyio
async def test_google_userinfo(monkeypatch):
    google = _userinfo(
        monkeypatch, 200, {"sub": "1", "email": "a@gmail.com", "email_verified": True}
    )
    assert await google.get_id_email("token") == ("1", "a@gmail.com")

    google = _userinfo(monkeypatch, 200, {"sub": "1", "email": "a@x.com", "email_verified": False})
    assert await google.get_id_email("token") == ("1", None)

    google = _userinfo(monkeypatch, 401, {"error": "invalid_token"})
    with pytest.raises(GetIdEmailError):
        await google.get_id_email("token")


def test_google_asks_only_openid_and_email():
    assert GoogleOpenID("id", "secret").base_scopes == ["openid", "email"]
