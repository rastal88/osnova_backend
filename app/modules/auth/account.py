"""The signed-in user's own account: password, email, sessions, deletion.

The name is changed with PATCH /auth/users/me. Every change here asks for the
current password, so a stolen session alone cannot take the account over. A user
who signs in only with a provider (no known password) sets one with "Forgot
password" first, and confirms deletion with the account's email instead.
"""

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from fastapi_users import InvalidPasswordException, exceptions
from pydantic import BaseModel, EmailStr, Field

from app.core.errors import AppError
from app.modules.auth.backend import auth_backend, fastapi_users
from app.modules.auth.hooks import delete_hooks
from app.modules.auth.limits import limited
from app.modules.auth.manager import UserManager, get_user_manager, send_user_mail
from app.modules.auth.models import User
from app.modules.auth.roles import Role
from app.modules.auth.schemas import UserRead
from app.modules.auth.sessions import now_for_sessions

logger = logging.getLogger(__name__)

current_user_token = fastapi_users.authenticator.current_user_token(active=True)

account_router = APIRouter(prefix="/me", dependencies=limited)


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


class EmailChange(BaseModel):
    password: str = Field(max_length=200)
    email: EmailStr


class AccountDelete(BaseModel):
    """The current password, or the account's email for provider-only accounts."""

    password: str | None = Field(None, max_length=200)
    email: str | None = Field(None, max_length=320)


def _password_ok(manager: UserManager, user: User, password: str | None) -> bool:
    if not password:
        return False
    verified, _ = manager.password_helper.verify_and_update(password, user.hashed_password)
    return verified


@account_router.post("/password", status_code=204)
async def change_password(
    data: PasswordChange,
    user_token: tuple[User, str] = Depends(current_user_token),
    manager: UserManager = Depends(get_user_manager),
    strategy=Depends(auth_backend.get_strategy),
) -> Response:
    """Set a new password; every other session ends, this one gets a new cookie."""
    user, _ = user_token
    if not _password_ok(manager, user, data.current_password):
        raise AppError(400, "current_password_wrong")
    try:
        await manager.validate_password(data.new_password, user)
    except InvalidPasswordException as exc:
        raise AppError(400, str(exc.reason)) from exc
    user = await manager.user_db.update(
        user,
        {
            "hashed_password": manager.password_helper.hash(data.new_password),
            "sessions_valid_after": now_for_sessions(),
        },
    )
    logger.info("User %s changed the password.", user.id)
    return await auth_backend.login(strategy, user)


@account_router.post("/email")
async def change_email(
    data: EmailChange,
    user_token: tuple[User, str] = Depends(current_user_token),
    manager: UserManager = Depends(get_user_manager),
) -> UserRead:
    """Move the account to a new email: it has to be confirmed again, the old address
    gets a notice."""
    user, _ = user_token
    if not _password_ok(manager, user, data.password):
        raise AppError(400, "current_password_wrong")
    email = str(data.email)
    if email.lower() != user.email.lower():
        try:
            await manager.get_by_email(email)
            raise AppError(400, "update_user_email_already_exists")
        except exceptions.UserNotExists:
            pass
    old_email = user.email
    user = await manager.user_db.update(user, {"email": email, "is_verified": False})
    logger.info("User %s changed the email.", user.id)
    await send_user_mail("email_changed", user, link="", to=old_email)
    await manager.request_verify(user)
    return UserRead.model_validate(user, from_attributes=True)


@account_router.post("/sign-out-everywhere", status_code=204)
async def sign_out_everywhere(
    user_token: tuple[User, str] = Depends(current_user_token),
    manager: UserManager = Depends(get_user_manager),
    strategy=Depends(auth_backend.get_strategy),
) -> Response:
    """End every session of this user, this one included."""
    user, token = user_token
    await manager.user_db.update(user, {"sessions_valid_after": now_for_sessions()})
    logger.info("User %s signed out everywhere.", user.id)
    return await auth_backend.logout(strategy, user, token)


@account_router.delete("", status_code=204)
async def delete_account(
    data: AccountDelete,
    user_token: tuple[User, str] = Depends(current_user_token),
    manager: UserManager = Depends(get_user_manager),
    strategy=Depends(auth_backend.get_strategy),
) -> Response:
    """Delete the account and its data for good (files, notifications, linked
    providers). Root cannot: the site needs one."""
    user, token = user_token
    if user.role == Role.ROOT:
        raise AppError(403, "root_cannot_delete_self")
    typed_email = (data.email or "").strip().lower()
    by_email = bool(user.oauth_accounts) and typed_email == user.email.lower()
    if not (_password_ok(manager, user, data.password) or by_email):
        raise AppError(400, "account_delete_not_confirmed")

    session = manager.user_db.session
    for hook in delete_hooks:
        await hook(session, user)
    response = await auth_backend.logout(strategy, user, token)
    await manager.user_db.delete(user)
    logger.info("User %s deleted the account.", user.id)
    return response
