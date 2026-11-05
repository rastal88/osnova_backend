from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_async_session
from app.core.roles import Role
from app.core.user.dependencies import require_any_role
from app.models.user import User

admin_flow_router = APIRouter()

@admin_flow_router.get("/main", tags=["admin"])
async def admin_dashboard(user: User = Depends(require_any_role(Role.ROOT, Role.MODERATOR))):
    return {"message": f"Welcome, {user.email}"}

@admin_flow_router.get("/users", tags=["admin"])
async def list_all_users(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_any_role(Role.ROOT, Role.MODERATOR))
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
