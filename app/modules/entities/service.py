from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.entities import EntityType, entity_types
from app.core.settings import keep_masked, mask_secrets, secret_fields
from app.modules.auth.encryption import decrypt_fields, encrypt_fields
from app.modules.auth.permissions import permission
from app.modules.entities.models import Entity

# Create, change and delete entities, send a test message through a channel
ENTITIES_MANAGE = permission("entities.manage")


def plain_params(entity: Entity) -> dict[str, Any]:
    """The stored parameters with secrets decrypted (app/modules/auth/encryption.py)."""
    model = entity_types.get(entity.type)
    return decrypt_fields(entity.params, secret_fields(model)) if model else dict(entity.params)


def parse_params(entity: Entity) -> EntityType | None:
    """Typed parameters, or None for an unknown type or parameters that no longer validate."""
    model = entity_types.get(entity.type)
    if model is None:
        return None
    try:
        return model.model_validate(plain_params(entity))
    except ValidationError:
        return None


def masked(entity: Entity) -> dict[str, Any]:
    """Parameters for the API: secrets as SECRET_MASK."""
    model = entity_types.get(entity.type)
    return mask_secrets(model, entity.params) if model else dict(entity.params)


def validate_params(
    model: type[EntityType], params: dict[str, Any], stored: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Parameters to store: validated, a masked secret keeps the stored one, secrets
    encrypted. Raises ValidationError."""
    secrets = secret_fields(model)
    plain = keep_masked(model, params, decrypt_fields(stored or {}, secrets))
    return encrypt_fields(model.model_validate(plain).model_dump(mode="json"), secrets)


async def enabled_entities(session: AsyncSession, group: str) -> list[tuple[Entity, EntityType]]:
    """Enabled entities of a group with valid parameters, by name."""
    types = [name for name, model in entity_types.items() if model.group == group]
    if not types:
        return []
    rows = await session.scalars(
        select(Entity).where(Entity.type.in_(types), Entity.enabled.is_(True)).order_by(Entity.name)
    )
    return [(entity, params) for entity in rows if (params := parse_params(entity)) is not None]
