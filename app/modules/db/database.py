from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import config


class Base(DeclarativeBase):
    pass


engine = (
    create_async_engine(config.DATABASE_URL, echo=config.DB_ECHO) if config.DATABASE_URL else None
)
SessionLocal = (
    async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    if engine is not None
    else None
)


async def get_async_session() -> AsyncGenerator[AsyncSession]:
    if SessionLocal is None:
        raise RuntimeError("Database is not configured: set DATABASE_URL")
    async with SessionLocal() as session:
        yield session


@asynccontextmanager
async def app_session(app: FastAPI) -> AsyncIterator[AsyncSession]:
    """A session outside a route (middleware, hooks) that honours dependency overrides,
    so tests can point everything at their own database."""
    factory = app.dependency_overrides.get(get_async_session, get_async_session)
    sessions = factory()
    try:
        yield await anext(sessions)
    finally:
        await sessions.aclose()
