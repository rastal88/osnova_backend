import uuid

from fastapi_users import schemas
from pydantic import Field

from app.modules.auth.roles import Role


class UserRead(schemas.BaseUser[uuid.UUID]):
    role: Role


class UserCreate(schemas.BaseUserCreate):
    password: str = Field(min_length=8)


class UserUpdate(schemas.BaseUserUpdate):
    pass
