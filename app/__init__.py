from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import config
from .core.captcha import check_captcha_config
from .core.errors import add_exception_handlers, use_error_schema
from .core.logging_config import setup_logging
from .core.middlewares import add_middlewares
from .core.modules import ShutdownHook, load_modules
from .core.profile import check_profile
from .core.rate_limit import check_rate_limit_config
from .core.routes import core_router


def create_app() -> FastAPI:
    setup_logging()
    shutdown_hooks: list[ShutdownHook] = []

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        for hook in reversed(shutdown_hooks):
            await hook()

    # Interactive docs and the schema only in development: in production they map the API
    docs = config.DEBUG
    app = FastAPI(
        title=config.APP_NAME,
        version=config.APP_VERSION,
        lifespan=lifespan,
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
    )
    add_middlewares(app)
    add_exception_handlers(app)
    app.include_router(core_router, prefix="/api/v1")
    shutdown_hooks.extend(load_modules(app, config))
    check_profile(config.APP_PROFILE, app.state.modules, config.RATE_LIMIT_STORAGE)
    check_captcha_config()
    check_rate_limit_config()
    use_error_schema(app)

    return app


app = create_app()
