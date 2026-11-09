"""Client area: endpoints for any signed-in user.

A domain package of your own app: add endpoints to ``client_router`` (every one
requires sign-in) or copy this layout for a new domain and add it to
app/core/modules.py.
"""

from fastapi import FastAPI


def register(app: FastAPI):
    from .routes import client_router

    app.include_router(client_router, prefix="/api/v1/client", tags=["Client"])
    return None
