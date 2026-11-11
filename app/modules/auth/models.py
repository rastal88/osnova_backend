import uuid
from datetime import UTC, datetime

from fastapi import Depends
from fastapi_users_db_sqlalchemy import (
    SQLAlchemyBaseOAuthAccountTableUUID,
    SQLAlchemyBaseUserTableUUID,
    SQLAlchemyUserDatabase,
)
from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from app.modules.auth.permissions import all_permissions
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


class RoleRecord(Base):
    """A role: a named set of permissions (app/modules/auth/permissions.py)."""

    __tablename__ = "roles"

    # Stored in users.role and shown by the API; never changes
    slug: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    permissions: Mapped[list[str]] = mapped_column(JSON, default=list)
    # root, moderator and user (see Role): cannot be deleted
    system: Mapped[bool] = mapped_column(default=False)


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"

    role: Mapped[str] = mapped_column(
        String(50), ForeignKey("roles.slug"), default=Role.USER.value, index=True
    )
    # Loaded with the user: every request checks the permissions
    role_record: Mapped[RoleRecord] = relationship(lazy="selectin")
    date_created: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
    )
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Shown instead of the email where a name reads better; optional
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Sessions issued before this moment no longer sign in (sign out everywhere,
    # password change); see app/modules/auth/sessions.py
    sessions_valid_after: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Loaded with the user (async code cannot load it later); deleted with the user
    oauth_accounts: Mapped[list[OAuthAccount]] = relationship(
        lazy="selectin", cascade="all, delete-orphan"
    )

    @property
    def permissions(self) -> frozenset[str]:
        """What the user may do; root may do everything."""
        if self.role == Role.ROOT:
            return all_permissions()
        return all_permissions().intersection(self.role_record.permissions)


async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User, OAuthAccount)
