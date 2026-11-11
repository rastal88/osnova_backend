"""Admin module: the admin area API for users with the admin.access permission.

Enabled by ADMIN_ENABLED. Requires the auth module. Every endpoint added to
``admin_router`` is closed to everyone else.
"""

from fastapi import FastAPI


def register(app: FastAPI):
    from .routes import admin_router

    app.include_router(admin_router, prefix="/api/v1/admin", tags=["Admin"])
    return None
