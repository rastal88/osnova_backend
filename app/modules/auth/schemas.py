import uuid

from fastapi_users import schemas
from pydantic import ConfigDict, Field, computed_field, field_validator

from app.config import config
from app.modules.auth.roles import Area, user_areas


class UserRead(schemas.BaseUser[uuid.UUID]):
    # The slug of a role: "root", "moderator", "user" or one created in the admin
    role: str
    name: str | None = None
    # What the role allows; the frontend shows only the actions that will work
    permissions: list[str] = []

    @field_validator("permissions", mode="before")
    @classmethod
    def _sorted(cls, value) -> list[str]:
        return sorted(value)

    @computed_field
    @property
    def areas(self) -> list[Area]:
        """Areas the user can open; the frontend lands on the first one after sign-in."""
        return user_areas(self.permissions, config.ADMIN_ENABLED)


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
