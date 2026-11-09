from typing import Literal

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.bootstrap import BootstrapResponse, get_bootstrap_config
from app.core.forms.routes import forms_router
from app.core.readiness import run_checks

core_router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["ok"]


@core_router.get("/bootstrap", tags=["System"])
async def bootstrap() -> BootstrapResponse:
    return get_bootstrap_config()


class ReadyResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    # Each dependency of the enabled modules, e.g. {"database": true}
    checks: dict[str, bool]


@core_router.get("/health", tags=["System"])
async def health() -> HealthResponse:
    """Liveness: the process is running."""
    return HealthResponse(status="ok")


@core_router.get(
    "/ready",
    tags=["System"],
    responses={503: {"model": ReadyResponse, "description": "A dependency is down"}},
)
async def ready() -> ReadyResponse:
    """Readiness: the dependencies of the enabled modules answer (503 if one does not)."""
    results = await run_checks()
    body = ReadyResponse(status="ok" if all(results.values()) else "unavailable", checks=results)
    if body.status == "ok":
        return body
    return JSONResponse(body.model_dump(), status_code=503)  # type: ignore[return-value]


core_router.include_router(forms_router)
