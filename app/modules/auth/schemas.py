import uuid

from fastapi_users import schemas
from pydantic import Field, computed_field

from app.config import config
from app.modules.auth.roles import Area, Role, user_areas


class UserRead(schemas.BaseUser[uuid.UUID]):
    role: Role

    @computed_field
    @property
    def areas(self) -> list[Area]:
        """Areas the user can open; the frontend lands on the first one after sign-in."""
        return user_areas(self.role, config.ADMIN_ENABLED)


class UserCreate(schemas.BaseUserCreate):
    password: str = Field(min_length=8)


class UserUpdate(schemas.BaseUserUpdate):
    pass
