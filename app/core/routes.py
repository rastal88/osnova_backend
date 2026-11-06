from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.bootstrap import BootstrapResponse, get_bootstrap_config
from app.core.forms.routes import forms_router

core_router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["ok"]


@core_router.get("/bootstrap", tags=["System"])
async def bootstrap() -> BootstrapResponse:
    return get_bootstrap_config()


@core_router.get("/health", tags=["System"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


core_router.include_router(forms_router)
