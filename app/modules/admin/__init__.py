"""Admin module: endpoints for ROOT and MODERATOR roles.

Enabled by ADMIN_ENABLED. Requires the auth module.
"""

from fastapi import FastAPI


def register(app: FastAPI):
    from .routes import admin_flow_router

    app.include_router(admin_flow_router, prefix="/api/v1/admin_flow", tags=["Admin"])
    return None
