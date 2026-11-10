"""Admin → Users: list with search, filters and pages; block / unblock; change role.

The query matches the frontend DataTable: `q`, `page`, `size`, `sort` (`-` for
descending) and filters by column key with comma-separated values.
`GET /admin/users/export` takes the same query without pages and answers with a
CSV file of everything that matches.

Rules: nobody changes their own account or the root user; only root changes
roles (to user or moderator: there is one root); a moderator blocks and
unblocks ordinary users only.
"""

import logging
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.csv_export import Delimiter, csv_response
from app.core.errors import AppError
from app.core.i18n import translate
from app.modules.auth.dependencies import require_admin
from app.modules.auth.models import User
from app.modules.auth.roles import Role
from app.modules.db import app_session, get_async_session

logger = logging.getLogger(__name__)

users_router = APIRouter(prefix="/users")

SORT_COLUMNS = {
    "email": User.email,
    "role": User.role,
    "date_created": User.date_created,
    "last_login": User.last_login,
}
UserSort = Literal[tuple(f"{sign}{name}" for name in SORT_COLUMNS for sign in ("", "-"))]  # type: ignore[valid-type]
UserStatus = Literal["active", "blocked"]
EXPORT_COLUMNS = ("email", "name", "role", "active", "verified", "date_created", "last_login")


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


def _conditions(q: str, role: str | None, status: str | None) -> list[ColumnElement[bool]]:
    """What the list and the export show."""
    conditions: list[ColumnElement[bool]] = []
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
    return conditions


def _order(sort: str) -> ColumnElement[Any]:
    column = SORT_COLUMNS[sort.lstrip("-")]
    return column.desc().nulls_last() if sort.startswith("-") else column.asc().nulls_first()


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
    conditions = _conditions(q, role, status)
    total = await session.scalar(select(func.count()).select_from(User).where(*conditions))
    result = await session.scalars(
        select(User)
        .where(*conditions)
        .order_by(_order(sort), User.email)
        .offset((page - 1) * size)
        .limit(size)
    )
    return AdminUserPage(
        items=[AdminUser.model_validate(user, from_attributes=True) for user in result],
        total=total or 0,
    )


@users_router.get("/export", response_class=StreamingResponse)
async def export_users(
    request: Request,
    q: str = Query("", max_length=100, description="Part of the email or the name"),
    sort: UserSort = "-date_created",  # type: ignore[valid-type]
    role: str | None = Query(None, description="Comma-separated roles"),
    status: str | None = Query(None, description="Comma-separated: active, blocked"),
    delimiter: Delimiter | None = Query(None, description="Default: by the request language"),
    admin: User = Depends(require_admin),
) -> StreamingResponse:
    """Every user the list shows with this query, as a CSV file."""
    statement = select(User).where(*_conditions(q, role, status)).order_by(_order(sort), User.email)
    yes_no = {True: translate("export.yes"), False: translate("export.no")}

    async def rows() -> AsyncIterator[list[Any]]:
        count = 0
        # Its own session: the request's one may be closed before the file is sent
        async with app_session(request.app) as session:
            result = await session.stream_scalars(statement.execution_options(yield_per=500))
            async for user in result:
                count += 1
                yield [
                    user.email,
                    user.name,
                    user.role.value,
                    yes_no[user.is_active],
                    yes_no[user.is_verified],
                    user.date_created,
                    user.last_login,
                ]
        logger.info("User %s exported %d users.", admin.id, count)

    header = [translate(f"export.{column}") for column in EXPORT_COLUMNS]
    return csv_response("users", header, rows(), delimiter)


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
