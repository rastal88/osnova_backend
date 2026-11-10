import uuid

from fastapi_users import schemas
from pydantic import ConfigDict, Field, computed_field, field_validator

from app.config import config
from app.modules.auth.roles import Area, Role, user_areas


class UserRead(schemas.BaseUser[uuid.UUID]):
    role: Role
    name: str | None = None

    @computed_field
    @property
    def areas(self) -> list[Area]:
        """Areas the user can open; the frontend lands on the first one after sign-in."""
        return user_areas(self.role, config.ADMIN_ENABLED)


class UserCreate(schemas.BaseUserCreate):
    password: str = Field(min_length=8)
    name: str | None = Field(None, max_length=100)


class UserUpdate(schemas.CreateUpdateDictModel):
    """PATCH /auth/users/me: only the name. Password and email change through
    /auth/me/*, which ask for the current password."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, max_length=100)

    @field_validator("name")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None
