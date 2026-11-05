"""Auth module: registration, login, roles (fastapi-users, cookie transport).

Enabled by AUTH_ENABLED. Requires the db module and SECRET_KEY.
Sessions: AUTH_STRATEGY=jwt (default, stateless) or redis (needs REDIS_URL).
Requirements: requirements/auth.txt (+ requirements/redis.txt for redis)
"""

from fastapi import FastAPI


def register(app: FastAPI):
    from .routes import auth_router

    app.include_router(auth_router, prefix="/api/v1/auth")
    return None
