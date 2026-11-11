from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.access import access_router
from app.modules.admin.users import users_router
from app.modules.auth.dependencies import require_admin
from app.modules.auth.models import RoleRecord, User
from app.modules.db import get_async_session

# Every endpoint of the admin area requires the admin.access permission.
admin_router = APIRouter(dependencies=[Depends(require_admin)])


class AdminOverview(BaseModel):
    users: int
    active_users: int
    # By the slug of a role, every role of the project
    users_by_role: dict[str, int]


@admin_router.get("/overview")
async def admin_overview(session: AsyncSession = Depends(get_async_session)) -> AdminOverview:
    """Counters for the admin dashboard."""
    rows = await session.execute(select(User.role, func.count()).group_by(User.role))
    by_role = dict(rows.all())
    roles = await session.scalars(
        select(RoleRecord.slug).order_by(RoleRecord.system.desc(), RoleRecord.name)
    )
    active = await session.scalar(select(func.count()).where(User.is_active.is_(True)))
    return AdminOverview(
        users=sum(by_role.values()),
        active_users=active or 0,
        users_by_role={slug: by_role.get(slug, 0) for slug in roles},
    )


admin_router.include_router(users_router)
admin_router.include_router(access_router)
