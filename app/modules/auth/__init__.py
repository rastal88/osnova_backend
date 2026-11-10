"""Auth module: registration, login, roles (fastapi-users, cookie transport).

Enabled by AUTH_ENABLED. Requires the db module and SECRET_KEY.
Sessions: AUTH_STRATEGY=jwt (default, stateless) or redis (needs REDIS_URL).
Requirements: requirements/auth.txt (+ requirements/redis.txt for redis)
"""

from fastapi import FastAPI


def register(app: FastAPI):
    import logging

    import httpx
    from httpx_oauth.exceptions import HTTPXOAuthError

    from app.core.errors import error_response

    from .backend import redis
    from .routes import auth_router

    async def oauth_provider_error(request, exc: HTTPXOAuthError):
        # E.g. the provider refused the token: the user can try again, it is not our 500
        response = getattr(exc, "response", None)
        detail = response.text[:300] if response is not None else ""
        logging.getLogger(__name__).warning("OAuth provider error: %s %s", exc, detail)
        return error_response(400, "oauth_provider_error")

    async def oauth_provider_unreachable(request, exc: httpx.TransportError):
        # Only sign-in providers are called with httpx: the network or the provider is down
        logging.getLogger(__name__).warning("OAuth provider unreachable: %r", exc)
        return error_response(502, "oauth_provider_unavailable")

    app.add_exception_handler(HTTPXOAuthError, oauth_provider_error)
    app.add_exception_handler(httpx.TransportError, oauth_provider_unreachable)

    if redis is not None:
        from app.core.readiness import add_check

        async def redis_sessions() -> None:
            await redis.ping()

        add_check("redis", redis_sessions)

    app.include_router(auth_router, prefix="/api/v1/auth")
    return None
