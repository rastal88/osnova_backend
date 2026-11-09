import uuid
from datetime import UTC, datetime

from fastapi import Depends
from fastapi_users_db_sqlalchemy import (
    SQLAlchemyBaseOAuthAccountTableUUID,
    SQLAlchemyBaseUserTableUUID,
    SQLAlchemyUserDatabase,
)
from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import DateTime, ForeignKey
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from app.modules.auth.roles import Role
from app.modules.db import Base, get_async_session


class OAuthAccount(SQLAlchemyBaseOAuthAccountTableUUID, Base):
    """An external account (e.g. Google) the user signs in with."""

    __tablename__ = "oauth_accounts"

    # The base class points at a table named "user"; ours is "users"
    @declared_attr
    def user_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(
            GUID, ForeignKey("users.id", ondelete="cascade"), nullable=False, index=True
        )


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"

    role: Mapped[Role] = mapped_column(SQLEnum(Role), default=Role.USER)
    date_created: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
    )
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Loaded with the user (async code cannot load it later)
    oauth_accounts: Mapped[list[OAuthAccount]] = relationship(lazy="selectin")


async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User, OAuthAccount)
