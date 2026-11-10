import uuid

from fastapi_users import FastAPIUsers
from fastapi_users.authentication import AuthenticationBackend, CookieTransport

from app.config import config
from app.modules.auth.manager import get_user_manager
from app.modules.auth.models import User
from app.modules.auth.sessions import SessionJWTStrategy, SessionRedisStrategy

MIN_SECRET_LENGTH = 32
# Values from the docs that must never sign real tokens
PLACEHOLDER_SECRETS = {"change-me"}


def check_secret_key(value: str | None) -> None:
    if not value:
        raise RuntimeError("Auth module requires SECRET_KEY")
    if value in PLACEHOLDER_SECRETS or len(value) < MIN_SECRET_LENGTH:
        raise RuntimeError(
            f"SECRET_KEY is the example value or shorter than {MIN_SECRET_LENGTH} characters. "
            'Generate one: python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )


check_secret_key(config.SECRET_KEY)

lifetime_seconds = config.ACCESS_TOKEN_EXPIRE_MINUTES * 60

cookie_transport = CookieTransport(
    cookie_max_age=lifetime_seconds,
    cookie_secure=config.COOKIE_SECURE,
)

redis = None
if config.AUTH_STRATEGY == "redis":
    if not config.REDIS_URL:
        raise RuntimeError("AUTH_STRATEGY=redis requires REDIS_URL")
    import redis.asyncio as redis_asyncio

    redis = redis_asyncio.from_url(config.REDIS_URL, decode_responses=True)


def get_strategy() -> SessionJWTStrategy | SessionRedisStrategy:
    # JWT keeps the auth module stateless (no Redis); Redis allows server-side logout.
    # Both end every session of a user at once (app/modules/auth/sessions.py).
    if redis is not None:
        return SessionRedisStrategy(redis, lifetime_seconds=lifetime_seconds)
    return SessionJWTStrategy(
        secret=config.SECRET_KEY,
        lifetime_seconds=lifetime_seconds,
        algorithm=config.ALGORITHM,
    )


auth_backend = AuthenticationBackend(
    name="cookie",
    transport=cookie_transport,
    get_strategy=get_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [auth_backend],
)
