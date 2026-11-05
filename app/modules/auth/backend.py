import uuid

from fastapi_users import FastAPIUsers
from fastapi_users.authentication import (
    AuthenticationBackend,
    CookieTransport,
    JWTStrategy,
    RedisStrategy,
)

from app.config import config
from app.modules.auth.manager import get_user_manager
from app.modules.auth.models import User

if not config.SECRET_KEY:
    raise RuntimeError("Auth module requires SECRET_KEY")

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


def get_strategy() -> JWTStrategy | RedisStrategy:
    # JWT keeps the auth module stateless (no Redis); Redis allows server-side logout.
    if redis is not None:
        return RedisStrategy(redis, lifetime_seconds=lifetime_seconds)
    return JWTStrategy(
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
