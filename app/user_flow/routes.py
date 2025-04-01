from fastapi import APIRouter, Depends
from app.core.user.strategies import fastapi_users
from app.models.user import User

user_flow_router = APIRouter()

@user_flow_router.get("/main")
async def user_profile(user: User = Depends(fastapi_users.current_user())):
    return {"message": "User profile", "user_id": user.id}