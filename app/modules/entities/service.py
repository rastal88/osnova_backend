from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.entities import EntityType, entity_types
from app.core.settings import secret_fields
from app.modules.entities.models import Entity

# Sent instead of a stored secret; sent back unchanged, it keeps the stored value
SECRET_MASK = "********"


def parse_params(entity: Entity) -> EntityType | None:
    """Typed parameters, or None for an unknown type or parameters that no longer validate."""
    model = entity_types.get(entity.type)
    if model is None:
        return None
    try:
        return model.model_validate(entity.params)
    except ValidationError:
        return None


def masked(entity: Entity) -> dict[str, Any]:
    model = entity_types.get(entity.type)
    secrets = secret_fields(model) if model else set()
    return {
        key: (SECRET_MASK if key in secrets and value else value)
        for key, value in entity.params.items()
    }


def validate_params(
    model: type[EntityType], params: dict[str, Any], stored: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Validated parameters; a masked secret keeps the stored one. Raises ValidationError."""
    params = dict(params)
    for key in secret_fields(model):
        if params.get(key) == SECRET_MASK:
            params[key] = (stored or {}).get(key, "")
    return model.model_validate(params).model_dump(mode="json")


async def enabled_entities(session: AsyncSession, group: str) -> list[tuple[Entity, EntityType]]:
    """Enabled entities of a group with valid parameters, by name."""
    types = [name for name, model in entity_types.items() if model.group == group]
    if not types:
        return []
    rows = await session.scalars(
        select(Entity).where(Entity.type.in_(types), Entity.enabled.is_(True)).order_by(Entity.name)
    )
    return [(entity, params) for entity in rows if (params := parse_params(entity)) is not None]
