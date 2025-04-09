from datetime import datetime
from typing import Optional

from fastapi import Depends
from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID, SQLAlchemyUserDatabase
from sqlalchemy import DateTime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SQLEnum

from app.core.database import get_async_session
from app.core.roles import Role
from app.models import Base


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"

    role: Mapped[Role] = mapped_column(SQLEnum(Role), default=Role.USER)
    date_created: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=datetime.utcnow)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User)