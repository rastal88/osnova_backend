from fastapi import APIRouter, Depends, Request

from app.config import config
from app.core.rate_limit import RateLimiter, check_limit, client_address, parse_limit
from app.modules.auth.backend import auth_backend, fastapi_users
from app.modules.auth.oauth import oauth_clients, redirect_url
from app.modules.auth.schemas import UserCreate, UserRead, UserUpdate

rate_limit = parse_limit(config.AUTH_RATE_LIMIT)
limiter = RateLimiter(*rate_limit) if rate_limit else None


async def limit_by_ip(request: Request) -> None:
    """Slows down password guessing and sending emails to someone else's address."""
    check_limit(limiter, f"{request.url.path}:{client_address(request)}")


limited = [Depends(limit_by_ip)]

auth_router = APIRouter()

auth_router.include_router(
    fastapi_users.get_auth_router(auth_backend), tags=["auth"], dependencies=limited
)

auth_router.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate), tags=["auth"], dependencies=limited
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
