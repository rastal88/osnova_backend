import os
from pathlib import Path

# The test session runs with every module of the project enabled (`make strip` may have
# removed some: their flags stay off). Minimal-profile behaviour is checked in a separate
# process (see test_modules.py), because settings are read once at import time.
_MODULES_DIR = Path(__file__).resolve().parent.parent / "app" / "modules"


def _flag(module: str) -> str:
    return "true" if (_MODULES_DIR / module).is_dir() else "false"


os.environ.update(
    {
        "APP_NAME": "TestApp",
        "APP_VERSION": "1.0.0",
        "APP_PROFILE": "standard",
        "DEBUG": "true",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db",
        "SECRET_KEY": "test-secret-key-at-least-32-bytes-long",
        "AUTH_STRATEGY": "jwt",
        "AUTH_ENABLED": _flag("auth"),
        "ADMIN_ENABLED": _flag("admin"),
        "FILES_ENABLED": _flag("files"),
        "NOTIFICATIONS_ENABLED": _flag("notifications"),
        "BACKGROUND_TASKS_ENABLED": _flag("tasks"),
        "CELERY_BROKER_URL": "memory://",
        "CORS_ORIGINS": "http://localhost:5173",
        "GOOGLE_CLIENT_ID": "test-client-id",
        "GOOGLE_CLIENT_SECRET": "test-client-secret",
    }
)

from importlib.util import find_spec  # noqa: E402

import pytest  # noqa: E402
from fastapi import Depends  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import insert  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import create_app  # noqa: E402
from app.core.modules import MODULES  # noqa: E402
from app.modules.db import Base, get_async_session  # noqa: E402

# Modules of the registry that are in the project (`make strip` removes the others)
PRESENT = {spec.name for spec in MODULES if find_spec(spec.path)}

if "auth" in PRESENT:
    from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

    from app.modules.auth.models import OAuthAccount, RoleRecord, User, get_user_db

# The rows migration 0009 creates (tests build the tables from the models)
MODERATOR_PERMISSIONS = [
    "admin.access",
    "users.read",
    "users.export",
    "users.block",
    "leads.read",
    "leads.manage",
    "leads.export",
    "files.manage",
]
SYSTEM_ROLES = [
    {"slug": "root", "name": "Root", "permissions": [], "system": True},
    {
        "slug": "moderator",
        "name": "Moderator",
        "permissions": MODERATOR_PERMISSIONS,
        "system": True,
    },
    {"slug": "user", "name": "User", "permissions": [], "system": True},
]


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "modules(*names): the test needs these modules (app/core/modules.py); `make strip` "
        "deletes a test file marked with a module it removes, other tests are skipped",
    )


def pytest_collection_modifyitems(items):
    for item in items:
        needed = {name for mark in item.iter_markers("modules") for name in mark.args}
        if missing := sorted(needed - PRESENT):
            item.add_marker(pytest.mark.skip(reason=f"no module {', '.join(missing)}"))


@pytest.fixture
def eager_tasks(monkeypatch):
    """Celery runs the tasks inline (nothing to do in a project without background tasks)."""
    if "tasks" in PRESENT:
        from app.modules.tasks.celery_app import celery_app

        monkeypatch.setattr(celery_app.conf, "task_always_eager", True)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def database(tmp_path, monkeypatch):
    """An in-memory SQLite database with every table; returns the session factory."""
    if "files" in PRESENT:
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
        if "auth" in PRESENT:
            await conn.execute(insert(RoleRecord), SYSTEM_ROLES)

    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


def _app_with(session_factory):
    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_async_session] = override_session
    if "auth" in PRESENT:

        async def override_user_db(session=Depends(override_session)):
            yield SQLAlchemyUserDatabase(session, User, OAuthAccount)

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

    limiters = [limiter]
    if "auth" in PRESENT:
        from app.modules.auth.routes import limiter as auth_limiter

        limiters.append(auth_limiter)
    for item in limiters:
        if item is not None:
            item.hits.clear()
