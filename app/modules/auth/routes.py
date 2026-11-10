from fastapi import APIRouter, Depends

from app.config import config
from app.core.captcha import require_captcha
from app.modules.auth.account import account_router
from app.modules.auth.backend import auth_backend, fastapi_users
from app.modules.auth.limits import limited, limiter  # noqa: F401  limiter: reset by tests
from app.modules.auth.oauth import oauth_clients, redirect_url
from app.modules.auth.schemas import UserCreate, UserRead, UserUpdate

auth_router = APIRouter()

# The user's own password, email, sessions and deletion: /auth/me/*
auth_router.include_router(account_router, tags=["account"])

auth_router.include_router(
    fastapi_users.get_auth_router(auth_backend), tags=["auth"], dependencies=limited
)

auth_router.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    tags=["auth"],
    dependencies=[*limited, Depends(require_captcha)],
)

auth_router.include_router(
    fastapi_users.get_reset_password_router(), tags=["auth"], dependencies=limited
)

auth_router.include_router(
    fastapi_users.get_verify_router(UserRead), tags=["auth"], dependencies=limited
)

auth_router.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/users", tags=["users"]
)

for name, client in oauth_clients().items():
    auth_router.include_router(
        fastapi_users.get_oauth_router(
            client,
            auth_backend,
            config.SECRET_KEY,  # type: ignore[arg-type]
            redirect_url=redirect_url(name),
            # The provider has confirmed the email: link to an account with the same one
            associate_by_email=True,
            is_verified_by_default=True,
            csrf_token_cookie_secure=config.COOKIE_SECURE,
        ),
        prefix=f"/{name}",
        tags=["auth"],
    )
