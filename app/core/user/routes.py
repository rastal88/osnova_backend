from fastapi import APIRouter

from app.core.user.strategies import fastapi_users, auth_backend
from app.core.user.schemas import UserCreate, UserRead


auth_router = APIRouter()

auth_router.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/sing_in",

)

auth_router.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/sign-up",

)


#
# @auth_router.get("/google/login")
# async def login_via_google(request: Request):
#     redirect_uri = "http://localhost:8000/auth/google/callback"
#     return await oauth.google.authorize_redirect(request, redirect_uri)
#
# @auth_router.get("/google/callback")
# async def auth_via_google(request: Request):
#     token = await oauth.google.authorize_access_token(request)
#     user = await oauth.google.parse_id_token(request, token)
#     return RedirectResponse(url="/")