from typing import Any

from fastapi import APIRouter, Body, Depends
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.settings import SettingsGroup, settings
from app.core.settings.schema import SettingsGroupDescription, describe_group
from app.modules.auth.dependencies import require_admin, require_any_role
from app.modules.auth.roles import Role
from app.modules.db import get_async_session
from app.modules.settings.service import groups_by_name, save_settings

# Admin roles can see the settings; only root changes them.
settings_router = APIRouter(dependencies=[Depends(require_admin)])


def _get_group(name: str) -> type[SettingsGroup]:
    group = groups_by_name.get(name)
    if group is None:
        raise AppError(404, "settings_group_not_found")
    return group


@settings_router.get("")
async def list_settings() -> list[SettingsGroupDescription]:
    """Every group with its form description and current values."""
    return [describe_group(group, settings.get(group)) for group in groups_by_name.values()]


@settings_router.put("/{name}", dependencies=[Depends(require_any_role(Role.ROOT))])
async def update_settings(
    name: str,
    payload: dict[str, Any] = Body(...),
    session: AsyncSession = Depends(get_async_session),
) -> SettingsGroupDescription:
    group = _get_group(name)
    try:
        value = await save_settings(session, group, payload)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc
    return describe_group(group, value)
