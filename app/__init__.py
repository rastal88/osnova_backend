from fastapi import FastAPI

from .admin_flow.routes import admin_flow_router
from .core.database import init_db, engine
from .core.middlewares import add_middlewares
from .user_flow.routes import user_flow_router


def create_app() -> FastAPI:
    app = FastAPI(title="My FastAPI App", version="1.0.0")
    add_middlewares(app)

    app.include_router(admin_flow_router, prefix="/admin_flow")
    app.include_router(user_flow_router, prefix="/user_flow")


    @app.on_event("startup")
    async def startup():
        await init_db()

    @app.on_event("shutdown")
    async def shutdown():
        await engine.dispose()

    return app

app = create_app()