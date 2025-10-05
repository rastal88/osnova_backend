from fastapi import APIRouter

from app.core.user.strategies import fastapi_users, auth_backend
from app.core.user.schemas import UserCreate, UserRead, UserUpdate

auth_router = APIRouter()

auth_router.include_router(
    fastapi_users.get_auth_router(auth_backend),
    tags=["auth"]
)

auth_router.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    tags=["auth"]
)

auth_router.include_router(
    fastapi_users.get_reset_password_router(),
    tags=["auth"]
)

auth_router.include_router(
    fastapi_users.get_verify_router(UserRead),
    tags=["auth"],
)

auth_router.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"]
)


current_user = fastapi_users.current_user()