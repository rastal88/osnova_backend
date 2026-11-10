"""Admin → Users: list with search, filters and pages; block / unblock; change role.

The query matches the frontend DataTable: `q`, `page`, `size`, `sort` (`-` for
descending) and filters by column key with comma-separated values.

Rules: nobody changes their own account or the root user; only root changes
roles (to user or moderator: there is one root); a moderator blocks and
unblocks ordinary users only.
"""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.modules.auth.dependencies import require_admin
from app.modules.auth.models import User
from app.modules.auth.roles import Role
from app.modules.db import get_async_session

users_router = APIRouter(prefix="/users")

SORT_COLUMNS = {
    "email": User.email,
    "role": User.role,
    "date_created": User.date_created,
    "last_login": User.last_login,
}
UserSort = Literal[tuple(f"{sign}{name}" for name in SORT_COLUMNS for sign in ("", "-"))]  # type: ignore[valid-type]
UserStatus = Literal["active", "blocked"]


class AdminUser(BaseModel):
    id: uuid.UUID
    email: str
    name: str | None = None
    role: Role
    is_active: bool
    is_verified: bool
    date_created: datetime | None
    last_login: datetime | None


class AdminUserPage(BaseModel):
    items: list[AdminUser]
    total: int


class AdminUserUpdate(BaseModel):
    is_active: bool | None = None
    # Root is assigned only with `manage.py createroot`
    role: Literal[Role.USER, Role.MODERATOR] | None = None


def _values(raw: str | None, allowed: tuple[str, ...]) -> list[str]:
    """Comma-separated filter values; unknown ones are ignored."""
    return [value for value in (raw or "").split(",") if value in allowed]


@users_router.get("")
async def list_users(
    q: str = Query("", max_length=100, description="Part of the email or the name"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    sort: UserSort = "-date_created",  # type: ignore[valid-type]
    role: str | None = Query(None, description="Comma-separated roles"),
    status: str | None = Query(None, description="Comma-separated: active, blocked"),
    session: AsyncSession = Depends(get_async_session),
) -> AdminUserPage:
    conditions = []
    if search := q.strip():
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        conditions.append(
            or_(User.email.ilike(pattern, escape="\\"), User.name.ilike(pattern, escape="\\"))
        )
    if roles := _values(role, tuple(item.value for item in Role)):
        conditions.append(User.role.in_([Role(item) for item in roles]))
    if statuses := _values(status, ("active", "blocked")):
        conditions.append(User.is_active.in_([item == "active" for item in statuses]))

    column = SORT_COLUMNS[sort.lstrip("-")]
    order = column.desc().nulls_last() if sort.startswith("-") else column.asc().nulls_first()
    total = await session.scalar(select(func.count()).select_from(User).where(*conditions))
    result = await session.scalars(
        select(User)
        .where(*conditions)
        .order_by(order, User.email)
        .offset((page - 1) * size)
        .limit(size)
    )
    return AdminUserPage(
        items=[AdminUser.model_validate(user, from_attributes=True) for user in result],
        total=total or 0,
    )


@users_router.patch("/{user_id}")
async def update_user(
    user_id: uuid.UUID,
    changes: AdminUserUpdate,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
) -> AdminUser:
    user = await session.get(User, user_id)
    if user is None:
        raise AppError(404, "not_found")
    if user.id == admin.id:
        raise AppError(403, "admin_cannot_change_self")
    if user.role == Role.ROOT:
        raise AppError(403, "admin_root_protected")
    if admin.role != Role.ROOT and (changes.role is not None or user.role != Role.USER):
        raise AppError(403, "forbidden")

    if changes.is_active is not None:
        user.is_active = changes.is_active
    if changes.role is not None:
        user.role = changes.role
    await session.commit()
    return AdminUser.model_validate(user, from_attributes=True)
