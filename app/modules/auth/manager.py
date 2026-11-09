import logging
import uuid
from datetime import UTC, datetime
from urllib.parse import urlencode

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, InvalidPasswordException, UUIDIDMixin
from starlette.responses import Response

from app.config import config
from app.core.i18n import get_language
from app.core.mail import render_mail, send_mail
from app.core.settings import settings
from app.modules.auth.models import User, get_user_db
from app.modules.auth.roles import Role
from app.modules.auth.schemas import UserCreate
from app.settings import SiteSettings

logger = logging.getLogger(__name__)


def frontend_link(path: str, token: str) -> str:
    """A frontend page in the request language, e.g. /en/verify-email?token=..."""
    query = urlencode({"token": token})
    return f"{config.FRONTEND_URL.rstrip('/')}/{get_language()}{path}?{query}"


async def send_user_mail(name: str, user: User, link: str) -> None:
    site = settings.get(SiteSettings).name
    await send_mail(render_mail(name, user.email, site=site, link=link))


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
        # Sends the confirmation link (on_after_request_verify); accounts from an OAuth
        # provider come with a confirmed email
        if not user.is_verified:
            await self.request_verify(user, request)

    async def on_after_request_verify(self, user: User, token: str, request: Request | None = None):
        await send_user_mail("verify_email", user, frontend_link("/verify-email", token))

    async def on_after_verify(self, user: User, request: Request | None = None):
        logger.info("User %s has confirmed the email.", user.id)

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
        logger.info("User %s requested a password reset.", user.id)
        await send_user_mail("reset_password", user, frontend_link("/reset-password", token))

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
