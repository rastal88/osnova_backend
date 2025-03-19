from fastapi import APIRouter, Depends
from app.core.user.dependencies import get_current_user
from app.models.user import User
from app.core.permissions import check_permission

user_flow_router = APIRouter()

@user_flow_router.get("/main")
async def get_user_data(current_user: User = Depends(get_current_user)):
    print(121342134234)
    check_permission(current_user.role, "read_own_data")
    return {"message": "This is user data"}