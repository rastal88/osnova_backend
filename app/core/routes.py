from fastapi import APIRouter

from app.core.bootstrap import get_bootstrap_config

core_router = APIRouter()


@core_router.get("/bootstrap", tags=["System"])
async def bootstrap():
    return get_bootstrap_config()


@core_router.get("/health", tags=["System"])
async def health():
    return {"status": "ok"}
