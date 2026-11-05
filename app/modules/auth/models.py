from datetime import UTC, datetime

from fastapi import Depends
from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID, SQLAlchemyUserDatabase
from sqlalchemy import DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.auth.roles import Role
from app.modules.db import Base, get_async_session


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"

    role: Mapped[Role] = mapped_column(SQLEnum(Role), default=Role.USER)
    date_created: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
    )
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User)
