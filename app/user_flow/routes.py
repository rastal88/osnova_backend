from fastapi import APIRouter, Depends

from app.modules.auth.dependencies import current_user
from app.modules.auth.models import User

user_flow_router = APIRouter()


@user_flow_router.get("/main")
async def user_profile(user: User = Depends(current_user)):
    return {"email": user.email, "role": user.role}
