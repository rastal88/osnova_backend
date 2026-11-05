import os

os.environ.update(
    {
        "BACKGROUND_TASKS_ENABLED": "false",
        "APP_NAME": "TestApp",
        "APP_VERSION": "1.0.0",
        "APP_PROFILE": "minimal",
        "APP_HOST": "localhost",
        "APP_PORT": "8000",
        "DEBUG": "true",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db",
        "SECRET_KEY": "supersecretkey",
        "ALGORITHM": "HS256",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "30",
        "COOKIE_SECURE": "false",
        "REDIS_URL": "redis://localhost:6379",
        "CELERY_BROKER_URL": "redis://localhost:6379",
        "CELERY_RESULT_BACKEND": "redis://localhost:6379",
        "AUTH_ENABLED": "true",
        "ADMIN_ENABLED": "true",
        "FILES_ENABLED": "true",
        "NOTIFICATIONS_ENABLED": "true",
        "OAUTH2_CLIENT_ID": "",
        "OAUTH2_CLIENT_SECRET": "",
        "OAUTH2_REDIRECT_URI": "",
        "CORS_ORIGINS": "http://localhost:5173",
    }
)

import fakeredis.aioredis
import pytest
from fastapi import Depends
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app import create_app
from app.core.database import Base, get_async_session
from app.core.user import strategies
from app.models.user import User, get_user_db


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def auth_client(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(strategies, "redis", fake_redis)

    async def override_session():
        async with session_factory() as session:
            yield session

    async def override_user_db(session=Depends(override_session)):
        yield SQLAlchemyUserDatabase(session, User)

    app = create_app()
    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_user_db] = override_user_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client, session_factory

    await fake_redis.aclose()
    await engine.dispose()
