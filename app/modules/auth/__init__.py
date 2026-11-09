"""Auth module: registration, login, roles (fastapi-users, cookie transport).

Enabled by AUTH_ENABLED. Requires the db module and SECRET_KEY.
Sessions: AUTH_STRATEGY=jwt (default, stateless) or redis (needs REDIS_URL).
Requirements: requirements/auth.txt (+ requirements/redis.txt for redis)
"""

from fastapi import FastAPI


def register(app: FastAPI):
    from .backend import redis
    from .routes import auth_router

    if redis is not None:
        from app.core.readiness import add_check

        async def redis_sessions() -> None:
            await redis.ping()

        add_check("redis", redis_sessions)

    app.include_router(auth_router, prefix="/api/v1/auth")
    return None
