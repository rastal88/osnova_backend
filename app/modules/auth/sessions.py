"""Sessions that can be ended for every device at once.

Each session records when it was issued: the `iat` claim of a JWT, or next to the
user id in Redis. A user's `sessions_valid_after` (set by "sign out everywhere", a
password change or reset) rejects every session issued before it, with either
strategy and without a list of sessions to keep.
"""

import secrets
import time
from datetime import UTC, datetime

import jwt
from fastapi_users import exceptions
from fastapi_users.authentication import JWTStrategy, RedisStrategy
from fastapi_users.jwt import decode_jwt, generate_jwt

from app.modules.auth.models import User


def now_for_sessions() -> datetime:
    """The moment to store in `sessions_valid_after` (whole seconds, like `iat`)."""
    return datetime.now(UTC).replace(tzinfo=None, microsecond=0)


def session_is_valid(user: User, issued_at: int | None) -> bool:
    if user.sessions_valid_after is None:
        return True
    if issued_at is None:
        return False
    return issued_at >= int(user.sessions_valid_after.replace(tzinfo=UTC).timestamp())


class SessionJWTStrategy(JWTStrategy):
    async def write_token(self, user: User) -> str:
        data = {"sub": str(user.id), "aud": self.token_audience, "iat": int(time.time())}
        return generate_jwt(data, self.encode_key, self.lifetime_seconds, algorithm=self.algorithm)

    async def read_token(self, token, user_manager):
        user = await super().read_token(token, user_manager)
        if user is None:
            return None
        try:
            data = decode_jwt(
                token, self.decode_key, self.token_audience, algorithms=[self.algorithm]
            )
        except jwt.PyJWTError:
            return None
        return user if session_is_valid(user, data.get("iat")) else None


class SessionRedisStrategy(RedisStrategy):
    """Stores "<user id>:<issued at>" under the token."""

    async def write_token(self, user: User) -> str:
        token = secrets.token_urlsafe()
        await self.redis.set(
            f"{self.key_prefix}{token}", f"{user.id}:{int(time.time())}", ex=self.lifetime_seconds
        )
        return token

    async def read_token(self, token, user_manager):
        if token is None:
            return None
        value = await self.redis.get(f"{self.key_prefix}{token}")
        if value is None:
            return None
        user_id, _, issued = value.partition(":")
        try:
            user = await user_manager.get(user_manager.parse_id(user_id))
        except (exceptions.UserNotExists, exceptions.InvalidID):
            return None
        return user if session_is_valid(user, int(issued) if issued else None) else None
