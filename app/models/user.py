from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID
from sqlalchemy import Column, Integer, String, Boolean, Enum

from app.core.roles import Role
from app.models import Base


class User(SQLAlchemyBaseUserTableUUID, Base):
    pass

