from fastapi import APIRouter, Depends, HTTPException
from app.core.user.dependencies import get_current_admin
from app.models.user import User
from app.core.permissions import check_permission

admin_flow_router = APIRouter()

@admin_flow_router.get("/main")
async def admin_dashboard(user: User = Depends(get_current_admin)):
    return {"message": "Admin dashboard", "user_id": user.id}

@admin_flow_router.get("/users")
async def list_users(user: User = Depends(get_current_admin)):
    return {"message": "List of all users"}