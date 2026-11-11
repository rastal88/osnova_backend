"""Admin → Users: list with search, filters and pages; block / unblock; change role.

The query matches the frontend DataTable: `q`, `page`, `size`, `sort` (`-` for
descending) and filters by column key with comma-separated values.
`GET /admin/users/export` takes the same query without pages and answers with a
CSV file of everything that matches.

Permissions: users.read (the list), users.export, users.block (block / unblock),
users.roles (give a role and groups; also needed to block someone who has a role
other than "user" or is in a group).
Nobody changes their own account or the root user (there is one root), and nobody
gives or manages more than they have themselves (app/modules/admin/access.py).
"""

import logging
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.csv_export import Delimiter, csv_response
from app.core.errors import AppError
from app.core.i18n import translate
from app.modules.admin.access import check_covers, check_covers_roles, roles_by_slug
from app.modules.admin.audit import Audit, audit_action, diff
from app.modules.auth.dependencies import require
from app.modules.auth.models import Group, User, role_permissions, user_groups
from app.modules.auth.permissions import permission
from app.modules.auth.roles import Role
from app.modules.db import app_session, get_async_session

logger = logging.getLogger(__name__)

USERS_READ = permission("users.read")
USERS_EXPORT = permission("users.export")
USERS_BLOCK = permission("users.block")
USERS_ROLES = permission("users.roles")

USERS_BLOCK_ACTION = audit_action("users.block")
USERS_UNBLOCK_ACTION = audit_action("users.unblock")
USERS_ACCESS_ACTION = audit_action("users.access")
USERS_EXPORT_ACTION = audit_action("users.export")

users_router = APIRouter(prefix="/users", dependencies=[Depends(require(USERS_READ))])

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
    language: str | None = None
    role: str
    # Ids of the groups the user is in
    groups: list[uuid.UUID] = []
    is_active: bool
    is_verified: bool
    date_created: datetime | None
    last_login: datetime | None

    @field_validator("groups", mode="before")
    @classmethod
    def _ids(cls, value) -> list:
        return [getattr(group, "id", group) for group in value]


class AdminUserPage(BaseModel):
    items: list[AdminUser]
    total: int


class AdminUserUpdate(BaseModel):
    is_active: bool | None = None
    # The slug of a role; root is assigned only with `manage.py createroot`
    role: str | None = None
    # Replaces the user's groups
    groups: list[uuid.UUID] | None = None


def _values(raw: str | None, allowed: tuple[str, ...]) -> list[str]:
    """Comma-separated filter values; unknown ones are ignored."""
    return [value for value in (raw or "").split(",") if value in allowed]


def _uuids(raw: str | None) -> list[uuid.UUID]:
    result = []
    for value in (raw or "").split(","):
        try:
            result.append(uuid.UUID(value))
        except ValueError:
            continue
    return result


def _conditions(
    q: str, role: str | None, status: str | None, group: str | None = None
) -> list[ColumnElement[bool]]:
    """What the list and the export show."""
    conditions: list[ColumnElement[bool]] = []
    if search := q.strip():
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        conditions.append(
            or_(User.email.ilike(pattern, escape="\\"), User.name.ilike(pattern, escape="\\"))
        )
    if roles := [value for value in (role or "").split(",") if value]:
        conditions.append(User.role.in_(roles))
    if groups := _uuids(group):
        members = select(user_groups.c.user_id).where(user_groups.c.group_id.in_(groups))
        conditions.append(User.id.in_(members))
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
    group: str | None = Query(None, description="Comma-separated group ids"),
    session: AsyncSession = Depends(get_async_session),
) -> AdminUserPage:
    conditions = _conditions(q, role, status, group)
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
    group: str | None = Query(None, description="Comma-separated group ids"),
    delimiter: Delimiter | None = Query(None, description="Default: by the request language"),
    admin: User = Depends(require(USERS_EXPORT)),
    audit: Audit = Depends(),
    session: AsyncSession = Depends(get_async_session),
) -> StreamingResponse:
    """Every user the list shows with this query, as a CSV file."""
    filters = {"q": q.strip(), "role": role, "status": status, "group": group}
    audit(USERS_EXPORT_ACTION, changes={key: value for key, value in filters.items() if value})
    await session.commit()
    statement = (
        select(User).where(*_conditions(q, role, status, group)).order_by(_order(sort), User.email)
    )
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
                    user.role,
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
    admin: User = Depends(require(USERS_READ)),
    audit: Audit = Depends(),
    session: AsyncSession = Depends(get_async_session),
) -> AdminUser:
    user = await session.get(User, user_id)
    if user is None:
        raise AppError(404, "not_found")
    if user.id == admin.id:
        raise AppError(403, "admin_cannot_change_self")
    if user.role == Role.ROOT:
        raise AppError(403, "admin_root_protected")
    access = changes.role is not None or changes.groups is not None
    needed = set()
    if changes.is_active is not None:
        needed.add(USERS_BLOCK)
    if access or user.role != Role.USER or user.groups:
        needed.add(USERS_ROLES)
    if not admin.permissions.issuperset(needed):
        raise AppError(403, "forbidden")
    check_covers(admin, user.held_permissions)

    if changes.is_active is not None and changes.is_active != user.is_active:
        user.is_active = changes.is_active
        action = USERS_UNBLOCK_ACTION if changes.is_active else USERS_BLOCK_ACTION
        audit(action, target_id=user.id, target=user.email)
    before = {"role": user.role, "groups": sorted(group.name for group in user.groups)}
    if changes.role is not None:
        (role,) = await roles_by_slug(session, [changes.role])
        check_covers(admin, role_permissions(role))
        user.role = role.slug
    if changes.groups is not None:
        wanted = set(changes.groups)
        groups = list(await session.scalars(select(Group).where(Group.id.in_(wanted))))
        if len(groups) != len(wanted):
            raise AppError(400, "group_unknown")
        for group in groups:
            check_covers_roles(admin, group.roles)
        user.groups = groups
    after = {"role": user.role, "groups": sorted(group.name for group in user.groups)}
    if access_changes := diff(before, after):
        audit(USERS_ACCESS_ACTION, target_id=user.id, target=user.email, changes=access_changes)
    await session.commit()
    return AdminUser.model_validate(user, from_attributes=True)
