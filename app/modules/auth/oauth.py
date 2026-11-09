"""Sign-in with external providers (OAuth 2, fastapi-users + httpx-oauth).

A provider is on when its keys are set in .env (Google: GOOGLE_CLIENT_ID and
GOOGLE_CLIENT_SECRET). The flow:

1. the frontend asks GET /auth/<provider>/authorize and opens `authorization_url`;
2. the provider sends the user back to <FRONTEND_URL>/oauth/<provider>/callback;
3. that page calls GET /auth/<provider>/callback with the same query string, which
   signs the user in (the usual auth cookie) — creating the account, or linking it
   to an existing one with the same email, since the provider confirmed it.

To add a provider: a client from httpx_oauth.clients in ``oauth_clients`` and
its keys in app/config.py (see app.core.capabilities.oauth_providers).
"""

from httpx_oauth.clients.google import GoogleOAuth2
from httpx_oauth.oauth2 import BaseOAuth2

from app.config import config
from app.core.capabilities import oauth_providers


def oauth_clients() -> dict[str, BaseOAuth2]:
    clients: dict[str, BaseOAuth2] = {}
    if "google" in oauth_providers(config):
        clients["google"] = GoogleOAuth2(config.GOOGLE_CLIENT_ID, config.GOOGLE_CLIENT_SECRET)  # type: ignore[arg-type]
    return clients


def redirect_url(provider: str) -> str:
    return f"{config.FRONTEND_URL.rstrip('/')}/oauth/{provider}/callback"
