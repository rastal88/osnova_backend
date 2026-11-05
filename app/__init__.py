from contextlib import asynccontextmanager
from fastapi import FastAPI

from .admin_flow.routes import admin_flow_router
from .core.celery_app import make_celery
from .core.database import init_db, engine
from .core.middlewares import add_middlewares
from .core.routes import core_router
from .core.user.routes import auth_router
from .user_flow.routes import user_flow_router
from .file_flow.routes import file_flow_router
from .config import config


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    if config.BACKGROUND_TASKS_ENABLED:
        make_celery()
    yield
    if engine is not None:
        await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=config.APP_NAME,
        version=config.APP_VERSION,
        lifespan=lifespan
    )
    add_middlewares(app)

    app.include_router(core_router, prefix="/api/v1")
    app.include_router(user_flow_router, prefix="/api/v1/user_flow", tags=["User"])
    if config.FILES_ENABLED:
        app.include_router(file_flow_router, prefix="/api/v1/file_flow", tags=["Files"])
    if config.AUTH_ENABLED:
        app.include_router(auth_router, prefix="/api/v1/auth", tags=["Auth"])
    if config.ADMIN_ENABLED:
        app.include_router(admin_flow_router, prefix="/api/v1/admin_flow", tags=["Admin"])

    return app

app = create_app()
