from fastapi import APIRouter, Depends

from app.core.roles import Role
from app.core.user.dependencies import require_role
from app.models.user import User

user_flow_router = APIRouter()

@user_flow_router.get("/main")
async def user_profile(user: User = Depends(require_role(Role.USER))):
    return {"email": user.email, "role": user.role}