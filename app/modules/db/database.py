from collections.abc import AsyncGenerator

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
