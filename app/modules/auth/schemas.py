import uuid

from fastapi_users import schemas
from pydantic import ConfigDict, Field, computed_field, field_validator
from pydantic_core import PydanticCustomError

from app.config import config
from app.core.languages import get_languages
from app.modules.auth.roles import Area, user_areas


class UserRead(schemas.BaseUser[uuid.UUID]):
    # The slug of a role: "root", "moderator", "user" or one created in the admin
    role: str
    name: str | None = None
    # Code of the user's language; null until chosen or for old accounts
    language: str | None = None
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
    """PATCH /auth/users/me: the name and the language. Password and email change
    through /auth/me/*, which ask for the current password."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, max_length=100)
    # One of the enabled languages (/bootstrap)
    language: str | None = None

    @field_validator("language")
    @classmethod
    def _enabled(cls, value: str | None) -> str | None:
        if value is not None and value not in get_languages().codes:
            raise PydanticCustomError("language_not_enabled", "Not an enabled language")
        return value

    @field_validator("name")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None
