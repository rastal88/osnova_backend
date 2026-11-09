"""Database module: async SQLAlchemy engine and sessions.

Enabled when DATABASE_URL is set. The schema is managed only by Alembic
migrations (``alembic upgrade head``), never created at startup.
Requirements: requirements/db.txt
"""

from fastapi import FastAPI

from .database import Base, app_session, engine, get_async_session, standalone_session

__all__ = [
    "Base",
    "app_session",
    "engine",
    "get_async_session",
    "register",
    "standalone_session",
]


def register(app: FastAPI):
    async def shutdown() -> None:
        if engine is not None:
            await engine.dispose()

    return shutdown
