import uuid
from datetime import datetime, timedelta
from typing import Optional, Union
from fastapi import Request
from fastapi import Depends
from fastapi_users import BaseUserManager, UUIDIDMixin, InvalidPasswordException
from starlette.responses import Response

from .schemas import UserCreate
from app.config import config

from ..roles import Role
from ...models import User
from ...models.user import get_user_db


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
        print(f"User {user.id} has registered.")

    async def on_after_login(
            self,
            user: User,
            request: Optional[Request] = None,
            response: Optional[Response] = None,
    ):
        update_data = {"last_login": datetime.utcnow()}
        await self.user_db.update(user, update_data)

    async def on_after_forgot_password(
            self, user: User, token: str, request: Optional[Request] = None
    ):
        print(f"User {user.id} has forgot their password. Reset token: {token}")

    async def on_after_reset_password(self, user: User, request: Optional[Request] = None):
        print(f"User {user.id} has reset their password.")


def get_user_manager(user_db = Depends(get_user_db)):
    yield UserManager(user_db)
