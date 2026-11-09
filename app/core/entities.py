"""Configurable entities: lists of similar records the owner edits in the admin
(lead delivery channels, later countries, payment methods...).

An entity type is a Pydantic model of its parameters, registered with
``@entity_type``. All entities live in one table `(type, name, enabled, params)`
(app/modules/entities), so a new kind is a class, not a table and a migration.
The admin form is generated from the model like a settings group: labels from
"entities.<type>.<field>", the type title from "entities.<type>.title".
Entities that need relations or heavy queries should become ordinary tables.
"""

from typing import ClassVar

from pydantic import BaseModel, ConfigDict


class EntityType(BaseModel):
    # Stored parameters of removed fields are ignored
    model_config = ConfigDict(extra="ignore")

    type: ClassVar[str]
    # Types shown together in the admin, e.g. "lead_channels"
    group: ClassVar[str]

    @classmethod
    def option_labels(cls, field: str) -> dict[str, str] | None:
        return None


entity_types: dict[str, type[EntityType]] = {}


def entity_type[E: type[EntityType]](cls: E) -> E:
    """Class decorator: make an entity type available to the admin."""
    entity_types[cls.type] = cls
    return cls
