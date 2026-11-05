from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import config

Base = declarative_base()

engine = (
    create_async_engine(config.DATABASE_URL, future=True, echo=True)
    if config.DATABASE_URL
    else None
)
SessionLocal = (
    async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    if engine is not None
    else None
)


async def init_db():
    if engine is None:
        return
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    if SessionLocal is None:
        raise RuntimeError("Database is not configured: set DATABASE_URL")
    async with SessionLocal() as session:
        yield session
