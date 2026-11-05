"""Example application ("client side") endpoints for any signed-in user.

A domain package of your own app: copy this layout for new ``<domain>_flow``
packages and add them to app/core/modules.py.
"""

from fastapi import FastAPI


def register(app: FastAPI):
    from .routes import user_flow_router

    app.include_router(user_flow_router, prefix="/api/v1/user_flow", tags=["User"])
    return None
