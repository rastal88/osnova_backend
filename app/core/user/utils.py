import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Union
from fastapi import Request
from fastapi import Depends
from fastapi_users import BaseUserManager, UUIDIDMixin, InvalidPasswordException
from starlette.responses import Response

from .schemas import UserCreate
from app.config import config
from app.core.roles import Role

from ...models import User
from ...models.user import get_user_db

logger = logging.getLogger(__name__)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = config.SECRET_KEY
    verification_token_secret = config.SECRET_KEY

    async def validate_password(
            self,
            password: str,
            user: Union[UserCreate, User],
    ) -> None:
        if len(password) < 8:
            raise InvalidPasswordException(
                reason="Password should be at least 8 characters"
            )
        if user.email in password:
            raise InvalidPasswordException(
                reason="Password should not contain e-mail"
            )

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        logger.info("User %s has registered.", user.id)

    async def on_after_login(
            self,
            user: User,
            request: Optional[Request] = None,
            response: Optional[Response] = None,
    ):
        update_data = {"last_login": datetime.now(timezone.utc).replace(tzinfo=None)}
        await self.user_db.update(user, update_data)

    async def on_after_forgot_password(
            self, user: User, token: str, request: Optional[Request] = None
    ):
        logger.info("User %s has forgot their password. Reset token: %s", user.id, token)

    async def on_after_reset_password(self, user: User, request: Optional[Request] = None):
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
            raise ValueError("ROOT user already exists. Only one ROOT user is allowed in the system.")

        user_create = UserCreate(**user_data)
        user = await self.create(user_create)
        user = await self.user_db.update(
            user,
            {"role": Role.ROOT, "is_superuser": True, "is_active": True},
        )
        return user


async def get_user_manager(user_db = Depends(get_user_db)):
    yield UserManager(user_db)
