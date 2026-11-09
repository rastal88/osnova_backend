import os

# The test session runs with every module enabled. Minimal-profile behaviour is
# checked in a separate process (see test_modules.py), because settings are
# read once at import time.
os.environ.update(
    {
        "APP_NAME": "TestApp",
        "APP_VERSION": "1.0.0",
        "APP_PROFILE": "standard",
        "DEBUG": "true",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db",
        "SECRET_KEY": "test-secret-key-at-least-32-bytes-long",
        "AUTH_STRATEGY": "jwt",
        "AUTH_ENABLED": "true",
        "ADMIN_ENABLED": "true",
        "FILES_ENABLED": "true",
        "NOTIFICATIONS_ENABLED": "true",
        "BACKGROUND_TASKS_ENABLED": "true",
        "CELERY_BROKER_URL": "memory://",
        "CORS_ORIGINS": "http://localhost:5173",
    }
)

import pytest  # noqa: E402
from fastapi import Depends  # noqa: E402
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import create_app  # noqa: E402
from app.modules.auth.models import User, get_user_db  # noqa: E402
from app.modules.db import Base, get_async_session  # noqa: E402


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def database(tmp_path, monkeypatch):
    """An in-memory SQLite database with every table; returns the session factory."""
    from app.modules.files import routes as file_routes
    from app.modules.files.storage import LocalStorage

    monkeypatch.setattr(file_routes, "get_storage", lambda: LocalStorage(tmp_path))

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


def _app_with(session_factory):
    async def override_session():
        async with session_factory() as session:
            yield session

    async def override_user_db(session=Depends(override_session)):
        yield SQLAlchemyUserDatabase(session, User)

    app = create_app()
    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_user_db] = override_user_db
    return app


@pytest.fixture
async def client(database):
    async with AsyncClient(
        transport=ASGITransport(app=_app_with(database)),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
async def auth_client(database):
    async with AsyncClient(
        transport=ASGITransport(app=_app_with(database)),
        base_url="http://test",
    ) as ac:
        yield ac, database


async def register(client, email: str, password: str = "password123"):
    return await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )


async def login(client, email: str, password: str = "password123"):
    return await client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )


async def create_user(session_factory, email: str, role: str, password: str = "password123"):
    from app.modules.auth.manager import UserManager
    from app.modules.auth.schemas import UserCreate

    async with session_factory() as session:
        manager = UserManager(SQLAlchemyUserDatabase(session, User))
        user = await manager.create(UserCreate(email=email, password=password))
        await manager.user_db.update(user, {"role": role})
        await session.commit()


@pytest.fixture(autouse=True)
def reset_settings():
    from app.core.settings import settings

    yield
    settings.reset()


@pytest.fixture(autouse=True)
def reset_rate_limits():
    from app.core.forms.routes import limiter

    if limiter is not None:
        limiter.hits.clear()
