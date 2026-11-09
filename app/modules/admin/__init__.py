"""Admin module: the admin area API for the ROOT and MODERATOR roles.

Enabled by ADMIN_ENABLED. Requires the auth module. Every endpoint added to
``admin_router`` is closed to other roles.
"""

from fastapi import FastAPI


def register(app: FastAPI):
    from .routes import admin_router

    app.include_router(admin_router, prefix="/api/v1/admin", tags=["Admin"])
    return None
