import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.entities import EntityType, entity_types
from app.core.errors import AppError
from app.core.forms.schema import FormFieldDescription
from app.core.i18n import translate
from app.core.settings.schema import describe_field
from app.modules.auth.dependencies import require_admin, require_any_role
from app.modules.auth.roles import Role
from app.modules.db import get_async_session
from app.modules.entities.models import Entity
from app.modules.entities.service import masked, validate_params

# Admin roles see the entities; only root changes them.
entities_router = APIRouter(dependencies=[Depends(require_admin)])
root_only = [Depends(require_any_role(Role.ROOT))]


class EntityTypeDescription(BaseModel):
    type: str
    group: str
    title: str
    fields: list[FormFieldDescription]


class EntityRead(BaseModel):
    id: uuid.UUID
    type: str
    name: str
    enabled: bool
    # Secret parameters are replaced by "********"
    params: dict[str, Any]
    created_at: datetime


class EntityCreate(BaseModel):
    type: str
    name: str = Field(min_length=1, max_length=100)
    enabled: bool = True
    params: dict[str, Any] = {}


class EntityUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    enabled: bool | None = None
    params: dict[str, Any] | None = None


def describe_type(model: type[EntityType]) -> EntityTypeDescription:
    key = f"entities.{model.type}"
    return EntityTypeDescription(
        type=model.type,
        group=model.group,
        title=translate(f"{key}.title"),
        fields=[
            describe_field(name, info, key, model.option_labels(name))
            for name, info in model.model_fields.items()
        ],
    )


def read(entity: Entity) -> EntityRead:
    return EntityRead(
        id=entity.id,
        type=entity.type,
        name=entity.name,
        enabled=entity.enabled,
        params=masked(entity),
        created_at=entity.created_at,
    )


def _params(model: type[EntityType], params: dict, stored: dict | None = None) -> dict:
    try:
        return validate_params(model, params, stored)
    except ValidationError as exc:
        # Field errors point at "params.<field>"
        errors = [{**error, "loc": ("params", *error["loc"])} for error in exc.errors()]
        raise RequestValidationError(errors) from exc


@entities_router.get("/types")
async def list_types(group: str | None = None) -> list[EntityTypeDescription]:
    """Entity types with their form description, in the request language."""
    return [
        describe_type(model)
        for model in entity_types.values()
        if group is None or model.group == group
    ]


@entities_router.get("")
async def list_entities(
    group: str | None = Query(None, description="Only types of this group"),
    session: AsyncSession = Depends(get_async_session),
) -> list[EntityRead]:
    types = [name for name, model in entity_types.items() if group in (None, model.group)]
    rows = await session.scalars(
        select(Entity).where(Entity.type.in_(types)).order_by(Entity.name, Entity.created_at)
    )
    return [read(entity) for entity in rows]


@entities_router.post("", status_code=201, dependencies=root_only)
async def create_entity(
    data: EntityCreate, session: AsyncSession = Depends(get_async_session)
) -> EntityRead:
    model = entity_types.get(data.type)
    if model is None:
        raise AppError(404, "not_found")
    entity = Entity(
        type=data.type, name=data.name, enabled=data.enabled, params=_params(model, data.params)
    )
    session.add(entity)
    await session.commit()
    return read(entity)


async def _get(session: AsyncSession, entity_id: uuid.UUID) -> Entity:
    entity = await session.get(Entity, entity_id)
    if entity is None or entity.type not in entity_types:
        raise AppError(404, "not_found")
    return entity


@entities_router.put("/{entity_id}", dependencies=root_only)
async def update_entity(
    entity_id: uuid.UUID, data: EntityUpdate, session: AsyncSession = Depends(get_async_session)
) -> EntityRead:
    entity = await _get(session, entity_id)
    if data.name is not None:
        entity.name = data.name
    if data.enabled is not None:
        entity.enabled = data.enabled
    if data.params is not None:
        entity.params = _params(entity_types[entity.type], data.params, entity.params)
    await session.commit()
    return read(entity)


@entities_router.delete("/{entity_id}", status_code=204, dependencies=root_only)
async def delete_entity(
    entity_id: uuid.UUID, session: AsyncSession = Depends(get_async_session)
) -> Response:
    await session.delete(await _get(session, entity_id))
    await session.commit()
    return Response(status_code=204)
