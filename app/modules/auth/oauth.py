"""Sign-in with external providers (OAuth 2, fastapi-users + httpx-oauth).

A provider is on when its keys are set in .env (Google: GOOGLE_CLIENT_ID and
GOOGLE_CLIENT_SECRET). The flow:

1. the frontend asks GET /auth/<provider>/authorize and opens `authorization_url`;
2. the provider sends the user back to <FRONTEND_URL>/oauth/<provider>/callback;
3. that page calls GET /auth/<provider>/callback with the same query string, which
   signs the user in (the usual auth cookie) — creating the account, or linking it
   to an existing one with the same email, since the provider confirmed it
   (UserManager.oauth_callback).

To add a provider: a client from httpx_oauth.clients in ``oauth_clients`` and
its keys in app/config.py (see app.core.capabilities.oauth_providers).
"""

import httpx
from httpx_oauth.clients.google import GoogleOAuth2
from httpx_oauth.exceptions import GetIdEmailError
from httpx_oauth.oauth2 import BaseOAuth2

from app.config import config
from app.core.capabilities import oauth_providers

GOOGLE_USERINFO = "https://openidconnect.googleapis.com/v1/userinfo"
# Seconds for each request to the provider (httpx waits 5 by default)
PROVIDER_TIMEOUT = 15


class GoogleOpenID(GoogleOAuth2):
    """Google through the OpenID Connect userinfo endpoint.

    The stock client asks the People API, which has to be enabled in Google Cloud
    separately; userinfo works with just the OAuth client and also says whether
    Google has confirmed the email.
    """

    def __init__(self, client_id: str, client_secret: str):
        super().__init__(client_id, client_secret, scopes=["openid", "email"])

    def get_httpx_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=PROVIDER_TIMEOUT)

    async def get_id_email(self, token: str) -> tuple[str, str | None]:
        async with self.get_httpx_client() as client:
            response = await client.get(
                GOOGLE_USERINFO,
                headers={**self.request_headers, "Authorization": f"Bearer {token}"},
            )
        if response.status_code >= 400:
            raise GetIdEmailError(response=response)
        data = response.json()
        # An unconfirmed email must not open (or be linked to) an account
        email = data.get("email") if data.get("email_verified") else None
        return data["sub"], email


def oauth_clients() -> dict[str, BaseOAuth2]:
    clients: dict[str, BaseOAuth2] = {}
    if "google" in oauth_providers(config):
        clients["google"] = GoogleOpenID(config.GOOGLE_CLIENT_ID, config.GOOGLE_CLIENT_SECRET)  # type: ignore[arg-type]
    return clients


def redirect_url(provider: str) -> str:
    return f"{config.FRONTEND_URL.rstrip('/')}/oauth/{provider}/callback"
