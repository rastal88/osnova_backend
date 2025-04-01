from fastapi import APIRouter, Request
from starlette.responses import RedirectResponse

from app.core.user.oauth import oauth
from app.core.user.schemas import UserCreate, UserDB
from app.core.user.strategies import auth_backend, fastapi_users


auth_router = APIRouter()


auth_router.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/jwt",
    tags=["jwt"],
)

auth_router.include_router(
    fastapi_users.get_register_router(UserDB, UserCreate),
    prefix="/reg",
    tags=["reg"],
)

@auth_router.get("/google/login")
async def login_via_google(request: Request):
    redirect_uri = "http://localhost:8000/auth/google/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)

@auth_router.get("/google/callback")
async def auth_via_google(request: Request):
    token = await oauth.google.authorize_access_token(request)
    user = await oauth.google.parse_id_token(request, token)
    return RedirectResponse(url="/")