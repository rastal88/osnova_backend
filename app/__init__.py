from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import config
from .core.logging_config import setup_logging
from .core.middlewares import add_middlewares
from .core.modules import ShutdownHook, load_modules
from .core.routes import core_router


def create_app() -> FastAPI:
    setup_logging()
    shutdown_hooks: list[ShutdownHook] = []

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        for hook in reversed(shutdown_hooks):
            await hook()

    app = FastAPI(
        title=config.APP_NAME,
        version=config.APP_VERSION,
        lifespan=lifespan,
    )
    add_middlewares(app)
    app.include_router(core_router, prefix="/api/v1")
    shutdown_hooks.extend(load_modules(app, config))

    return app


app = create_app()
