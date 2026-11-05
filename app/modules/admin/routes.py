from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.dependencies import require_any_role
from app.modules.auth.models import User
from app.modules.auth.roles import Role
from app.modules.db import get_async_session

admin_flow_router = APIRouter()


@admin_flow_router.get("/main", tags=["admin"])
async def admin_dashboard(user: User = Depends(require_any_role(Role.ROOT, Role.MODERATOR))):
    return {"message": f"Welcome, {user.email}"}


@admin_flow_router.get("/users", tags=["admin"])
async def list_all_users(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_any_role(Role.ROOT, Role.MODERATOR)),
):
    result = await session.execute(select(User))
    users = result.scalars().all()
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "role": u.role,
            "is_active": u.is_active,
            "is_superuser": u.is_superuser,
            "is_verified": u.is_verified,
        }
        for u in users
    ]
