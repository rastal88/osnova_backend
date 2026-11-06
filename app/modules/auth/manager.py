import logging
import uuid
from datetime import UTC, datetime

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, InvalidPasswordException, UUIDIDMixin
from starlette.responses import Response

from app.config import config
from app.modules.auth.models import User, get_user_db
from app.modules.auth.roles import Role
from app.modules.auth.schemas import UserCreate

logger = logging.getLogger(__name__)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = config.SECRET_KEY
    verification_token_secret = config.SECRET_KEY

    async def validate_password(
        self,
        password: str,
        user: UserCreate | User,
    ) -> None:
        if len(password) < 8:
            raise InvalidPasswordException(reason="password_too_short")
        if user.email in password:
            raise InvalidPasswordException(reason="password_contains_email")

    async def on_after_register(self, user: User, request: Request | None = None):
        logger.info("User %s has registered.", user.id)

    async def on_after_login(
        self,
        user: User,
        request: Request | None = None,
        response: Response | None = None,
    ):
        update_data = {"last_login": datetime.now(UTC).replace(tzinfo=None)}
        await self.user_db.update(user, update_data)

    async def on_after_forgot_password(
        self, user: User, token: str, request: Request | None = None
    ):
        # No email delivery yet: expose the token in logs only in DEBUG for local testing.
        if config.DEBUG:
            logger.info("User %s requested a password reset. Token: %s", user.id, token)
        else:
            logger.info("User %s requested a password reset.", user.id)

    async def on_after_reset_password(self, user: User, request: Request | None = None):
        logger.info("User %s has reset their password.", user.id)

    async def create_superuser(self, user_data: dict) -> User:
        """
        Creates a superuser (root).
        user_data: {"email": str, "password": str}

        There can only be one ROOT user in the system.
        """
        from sqlalchemy import select

        stmt = select(User).where(User.role == Role.ROOT)
        result = await self.user_db.session.execute(stmt)
        existing_root = result.scalars().first()

        if existing_root:
            raise ValueError(
                "ROOT user already exists. Only one ROOT user is allowed in the system."
            )

        user_create = UserCreate(**user_data)
        user = await self.create(user_create)
        user = await self.user_db.update(
            user,
            {"role": Role.ROOT, "is_superuser": True, "is_active": True},
        )
        return user


async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)
