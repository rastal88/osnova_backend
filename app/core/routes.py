from fastapi import APIRouter

from app.core.bootstrap import get_bootstrap_config
from app.core.forms.routes import forms_router

core_router = APIRouter()


@core_router.get("/bootstrap", tags=["System"])
async def bootstrap():
    return get_bootstrap_config()


@core_router.get("/health", tags=["System"])
async def health():
    return {"status": "ok"}


core_router.include_router(forms_router)
