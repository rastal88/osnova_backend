import uuid
import redis.asyncio

from fastapi_users import FastAPIUsers
from fastapi_users.authentication import AuthenticationBackend, CookieTransport, RedisStrategy

from app.config import config
from app.core.user.utils import get_user_manager
from app.models import User


cookie_transport = CookieTransport(
    cookie_max_age=3600,
    cookie_secure=config.COOKIE_SECURE,
)
redis = redis.asyncio.from_url(
    config.REDIS_URL or "redis://localhost:6379",
    decode_responses=True,
)


def get_redis_strategy() -> RedisStrategy:
    return RedisStrategy(redis, lifetime_seconds=3600)

auth_backend = AuthenticationBackend(
    name="cookie_redis_strategy",
    transport=cookie_transport,
    get_strategy=get_redis_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [auth_backend],
)