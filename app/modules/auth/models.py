import uuid
from datetime import UTC, datetime

from fastapi import Depends
from fastapi_users_db_sqlalchemy import (
    SQLAlchemyBaseOAuthAccountTableUUID,
    SQLAlchemyBaseUserTableUUID,
    SQLAlchemyUserDatabase,
)
from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import JSON, Column, DateTime, ForeignKey, String, Table
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from app.modules.auth.encryption import EncryptedText
from app.modules.auth.permissions import all_permissions, everyone_permissions
from app.modules.auth.roles import Role
from app.modules.db import Base, get_async_session


class OAuthAccount(SQLAlchemyBaseOAuthAccountTableUUID, Base):
    """An external account (e.g. Google) the user signs in with."""

    __tablename__ = "oauth_accounts"

    # The provider's tokens are stored encrypted (migration 0013)
    access_token: Mapped[str] = mapped_column(EncryptedText, nullable=False)
    refresh_token: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)

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


def role_permissions(role: RoleRecord) -> set[str]:
    """What a role gives, as stored (also of modules switched off now). The role of
    every new account gives only permissions meant for everyone: staff permissions
    stored there by mistake do nothing."""
    if role.slug == Role.USER:
        return set(everyone_permissions().intersection(role.permissions))
    return set(role.permissions)


group_roles = Table(
    "group_roles",
    Base.metadata,
    Column("group_id", GUID, ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
    Column("role", String(50), ForeignKey("roles.slug", ondelete="CASCADE"), primary_key=True),
)

user_groups = Table(
    "user_groups",
    Base.metadata,
    Column("user_id", GUID, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "group_id",
        GUID,
        ForeignKey("groups.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
)


class Group(Base):
    """People who get the same roles on top of their own, e.g. a department."""

    __tablename__ = "groups"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    roles: Mapped[list[RoleRecord]] = relationship(
        secondary=group_roles, lazy="selectin", order_by=RoleRecord.slug
    )


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"

    role: Mapped[str] = mapped_column(
        String(50), ForeignKey("roles.slug"), default=Role.USER.value, index=True
    )
    # Loaded with the user: every request checks the permissions
    role_record: Mapped[RoleRecord] = relationship(lazy="selectin")
    groups: Mapped[list[Group]] = relationship(
        secondary=user_groups, lazy="selectin", order_by=Group.name
    )
    date_created: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
    )
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Shown instead of the email where a name reads better; optional
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Emails and notifications go in it (app.core.i18n.user_language); empty for
    # accounts made before it existed: the request language then
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # Sessions issued before this moment no longer sign in (sign out everywhere,
    # password change); see app/modules/auth/sessions.py
    sessions_valid_after: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Loaded with the user (async code cannot load it later); deleted with the user
    oauth_accounts: Mapped[list[OAuthAccount]] = relationship(
        lazy="selectin", cascade="all, delete-orphan"
    )

    @property
    def held_permissions(self) -> frozenset[str]:
        """Every permission of their role and of the roles of their groups, also those
        of modules switched off now (they work again when the module is on)."""
        held = role_permissions(self.role_record)
        for group in self.groups:
            for role in group.roles:
                held.update(role_permissions(role))
        return frozenset(held)

    @property
    def permissions(self) -> frozenset[str]:
        """What the user may do now: the held permissions of the enabled modules; root
        may do everything."""
        if self.role == Role.ROOT:
            return all_permissions()
        return all_permissions().intersection(self.held_permissions)


async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User, OAuthAccount)
