import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.dependencies import require_admin
from app.modules.auth.models import User
from app.modules.auth.roles import Role
from app.modules.db import get_async_session

# Every endpoint of the admin area requires an admin role (see ADMIN_ROLES).
admin_router = APIRouter(dependencies=[Depends(require_admin)])


class AdminOverview(BaseModel):
    users: int
    active_users: int
    users_by_role: dict[Role, int]


class AdminUser(BaseModel):
    id: uuid.UUID
    email: str
    role: Role
    is_active: bool
    is_verified: bool


@admin_router.get("/overview")
async def admin_overview(session: AsyncSession = Depends(get_async_session)) -> AdminOverview:
    """Counters for the admin dashboard."""
    rows = await session.execute(select(User.role, func.count()).group_by(User.role))
    by_role = dict(rows.all())
    active = await session.scalar(select(func.count()).where(User.is_active.is_(True)))
    return AdminOverview(
        users=sum(by_role.values()),
        active_users=active or 0,
        users_by_role={role: by_role.get(role, 0) for role in Role},
    )


@admin_router.get("/users")
async def list_users(session: AsyncSession = Depends(get_async_session)) -> list[AdminUser]:
    result = await session.execute(select(User).order_by(User.email))
    return [AdminUser.model_validate(user, from_attributes=True) for user in result.scalars()]
