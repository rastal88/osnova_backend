from fastapi import APIRouter, Depends

from app.core.permissions import has_permission
from app.core.roles import Role
from app.core.user.dependencies import get_current_admin, require_role, require_any_role
from app.models.user import User


admin_flow_router = APIRouter()

@admin_flow_router.get("/main", tags=["admin"])
async def admin_dashboard(user: User = Depends(require_any_role(Role.ROOT, Role.MODERATOR))):
    return {"message": f"Welcome, {user.email}"}

@admin_flow_router.get("/admin/users", dependencies=[has_permission("manage_users")])
async def list_all_users():
    return {"users": [...]}