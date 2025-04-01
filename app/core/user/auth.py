from fastapi import Depends
from fastapi_users import BaseUserManager
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

from .schemas import UserCreate
from app.config import config
from ..database import get_user_db
from ...models import User


class UserManager(BaseUserManager[UserCreate, User]):
    reset_password_token_secret = config.SECRET_KEY
    verification_token_secret = config.SECRET_KEY

    async def on_after_register(self, user: User, request=None):
        print(f"User {user.id} has registered.")

    async def on_after_forgot_password(self, user: User, token: str, request=None):
        print(f"User {user.id} has forgot their password. Reset token: {token}")


def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)