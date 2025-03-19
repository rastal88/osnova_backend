from fastapi import APIRouter, Depends, HTTPException
from app.core.user.dependencies import get_current_user
from app.models.user import User
from app.core.permissions import check_permission

admin_flow_router = APIRouter()

@admin_flow_router.get("/main")
async def get_all_users(current_user: User = Depends(get_current_user)):
    check_permission(current_user.role, "read_all_data")
    return {"message": "This is admin data"}