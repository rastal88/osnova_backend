import redis.asyncio

from fastapi_users import FastAPIUsers
from fastapi_users.authentication import AuthenticationBackend, CookieTransport, RedisStrategy

from app.core.user.utils import get_user_manager
from app.models import User


cookie_transport = CookieTransport(cookie_max_age=3600)
redis = redis.asyncio.from_url("redis://localhost:6379", decode_responses=True)


def get_redis_strategy() -> RedisStrategy:
    return RedisStrategy(redis, lifetime_seconds=3600)

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=cookie_transport,
    get_strategy=get_redis_strategy,
)

fastapi_users = FastAPIUsers[User, int](
    get_user_manager,
    [auth_backend],
)
