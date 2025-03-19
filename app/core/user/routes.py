from urllib.request import Request

from fastapi import APIRouter
from fastapi_users import FastAPIUsers
from starlette.responses import RedirectResponse

from app.models.user import User
from app.core.user.oauth import oauth
from app.core.user.schemas import UserCreate, UserUpdate, UserDB
from app.core.user.dependencies import get_user_db
from app.core.user.strategies import jwt_authentication

router = APIRouter()

fastapi_users = FastAPIUsers(
    get_user_db,
    [jwt_authentication],
    User,
    UserCreate,
    UserUpdate,
    UserDB,
)

router.include_router(
    fastapi_users.get_auth_router(jwt_authentication),
    prefix="/auth/jwt",
    tags=["auth"],
)

router.include_router(
    fastapi_users.get_register_router(),
    prefix="/auth",
    tags=["auth"],
)

router.include_router(
    fastapi_users.get_users_router(),
    prefix="/users",
    tags=["users"],
)

@router.get("/auth/google/login")
async def login_via_google(request: Request):
    redirect_uri = "http://localhost:8000/auth/google/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/auth/google/callback")
async def auth_via_google(request: Request):
    token = await oauth.google.authorize_access_token(request)
    user = await oauth.google.parse_id_token(request, token)
    return RedirectResponse(url="/")