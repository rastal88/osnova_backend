"""Entities module: the table and admin API for configurable entities (app/core/entities).

Enabled together with the admin module. Admins see the entities, root changes
them; secret parameters (tokens, passwords) are never sent back in clear.
"""

from fastapi import FastAPI


def register(app: FastAPI):
    from .routes import entities_router

    app.include_router(entities_router, prefix="/api/v1/admin/entities", tags=["Admin"])
    return None
