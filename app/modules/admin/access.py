"""Admin → Roles and groups: who may do what.

A role is a set of permissions; a group gives its roles to everyone in it, on top
of each user's own role. Everyone in the admin area sees them, changes need
``roles.manage``. Roles and groups are given to users in Admin → Users
(``users.roles``).

Rules: nobody hands out more than they have themselves, so a role or a group can
be created, changed or removed only by someone who has every permission in it;
root has every permission and is not edited; the three built-in roles are not
renamed or deleted; a role that users have is not deleted.
"""

import re
import uuid
from collections.abc import Iterable

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.i18n import has_translation, translate
from app.modules.admin.audit import Audit, audit_action, diff
from app.modules.auth.dependencies import require
from app.modules.auth.models import Group, RoleRecord, User, group_roles, user_groups
from app.modules.auth.permissions import all_permissions, permission
from app.modules.auth.roles import Role
from app.modules.db import get_async_session

# Create, change and delete roles and groups
ROLES_MANAGE = permission("roles.manage")

ROLES_CREATE = audit_action("roles.create")
ROLES_UPDATE = audit_action("roles.update")
ROLES_DELETE = audit_action("roles.delete")
GROUPS_CREATE = audit_action("groups.create")
GROUPS_UPDATE = audit_action("groups.update")
GROUPS_DELETE = audit_action("groups.delete")

access_router = APIRouter()
manage = Depends(require(ROLES_MANAGE))


class PermissionRead(BaseModel):
    name: str
    title: str
    # The part before the dot, to show permissions in sections
    area: str
    area_title: str


class RoleRead(BaseModel):
    slug: str
    name: str
    permissions: list[str]
    system: bool
    # Users who have it as their own role
    users: int


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    permissions: list[str] = []


class RoleUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    permissions: list[str] | None = None


class GroupRead(BaseModel):
    id: uuid.UUID
    name: str
    roles: list[str]
    users: int


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    roles: list[str] = []


class GroupUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    roles: list[str] | None = None


def _text(key: str, fallback: str) -> str:
    """A project's own permission may have no text yet: its name is shown."""
    return translate(key) if has_translation(key) else fallback


def granted(role: RoleRecord) -> set[str]:
    """The permissions of a role that exist with the enabled modules."""
    if role.slug == Role.ROOT:
        return set(all_permissions())
    return all_permissions().intersection(role.permissions)


def check_covers(admin: User, permissions: Iterable[str]) -> None:
    """Nobody hands out, changes or takes away more than they have themselves."""
    if not admin.permissions.issuperset(permissions):
        raise AppError(403, "permission_not_allowed")


async def roles_by_slug(session: AsyncSession, slugs: Iterable[str]) -> list[RoleRecord]:
    """Roles that can be given to a user or a group: they exist and are not root."""
    wanted = sorted(set(slugs))
    if Role.ROOT in wanted:
        raise AppError(403, "role_protected")
    roles = list(await session.scalars(select(RoleRecord).where(RoleRecord.slug.in_(wanted))))
    if len(roles) != len(wanted):
        raise AppError(400, "role_unknown")
    return roles


def _known(permissions: Iterable[str]) -> set[str]:
    names = set(permissions)
    if not names <= all_permissions():
        raise AppError(400, "permission_unknown")
    return names


async def _slug(session: AsyncSession, name: str) -> str:
    """ "Sales team" -> "sales-team"; a name without Latin letters -> "role"."""
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "role"
    taken = set(await session.scalars(select(RoleRecord.slug)))
    slug, number = base, 1
    while slug in taken:
        number += 1
        slug = f"{base}-{number}"
    return slug


async def _role_read(session: AsyncSession, role: RoleRecord) -> RoleRead:
    users = await session.scalar(select(func.count()).where(User.role == role.slug))
    return RoleRead(
        slug=role.slug,
        name=role.name,
        permissions=sorted(granted(role)),
        system=role.system,
        users=users or 0,
    )


@access_router.get("/permissions")
async def list_permissions() -> list[PermissionRead]:
    """Every permission of the enabled modules, with texts in the request language."""
    result = []
    for name in sorted(all_permissions()):
        area = name.partition(".")[0]
        result.append(
            PermissionRead(
                name=name,
                title=_text(f"permissions.{name}", name),
                area=area,
                area_title=_text(f"permission_areas.{area}", area),
            )
        )
    return result


@access_router.get("/roles")
async def list_roles(session: AsyncSession = Depends(get_async_session)) -> list[RoleRead]:
    counts = dict(
        (await session.execute(select(User.role, func.count()).group_by(User.role))).all()
    )
    roles = await session.scalars(
        select(RoleRecord).order_by(RoleRecord.system.desc(), RoleRecord.name, RoleRecord.slug)
    )
    return [
        RoleRead(
            slug=role.slug,
            name=role.name,
            permissions=sorted(granted(role)),
            system=role.system,
            users=counts.get(role.slug, 0),
        )
        for role in roles
    ]


@access_router.post("/roles", status_code=201)
async def create_role(
    data: RoleCreate,
    admin: User = manage,
    audit: Audit = Depends(),
    session: AsyncSession = Depends(get_async_session),
) -> RoleRead:
    permissions = _known(data.permissions)
    check_covers(admin, permissions)
    role = RoleRecord(
        slug=await _slug(session, data.name), name=data.name, permissions=sorted(permissions)
    )
    session.add(role)
    audit(
        ROLES_CREATE,
        target_id=role.slug,
        target=role.name,
        changes=diff({}, {"name": role.name, "permissions": role.permissions}),
    )
    await session.commit()
    return await _role_read(session, role)


async def _editable_role(session: AsyncSession, slug: str, admin: User) -> RoleRecord:
    role = await session.get(RoleRecord, slug)
    if role is None:
        raise AppError(404, "not_found")
    if role.slug == Role.ROOT:
        raise AppError(403, "role_protected")
    check_covers(admin, granted(role))
    return role


@access_router.put("/roles/{slug}")
async def update_role(
    slug: str,
    data: RoleUpdate,
    admin: User = manage,
    audit: Audit = Depends(),
    session: AsyncSession = Depends(get_async_session),
) -> RoleRead:
    role = await _editable_role(session, slug, admin)
    before = {"name": role.name, "permissions": list(role.permissions)}
    if data.name is not None and data.name != role.name:
        if role.system:
            raise AppError(403, "role_protected")
        role.name = data.name
    if data.permissions is not None:
        permissions = _known(data.permissions)
        check_covers(admin, permissions)
        # Permissions of a module that is switched off stay with the role
        hidden = set(role.permissions) - all_permissions()
        role.permissions = sorted(permissions | hidden)
    if changes := diff(before, {"name": role.name, "permissions": role.permissions}):
        audit(ROLES_UPDATE, target_id=role.slug, target=role.name, changes=changes)
    await session.commit()
    return await _role_read(session, role)


@access_router.delete("/roles/{slug}", status_code=204)
async def delete_role(
    slug: str,
    admin: User = manage,
    audit: Audit = Depends(),
    session: AsyncSession = Depends(get_async_session),
) -> Response:
    role = await _editable_role(session, slug, admin)
    if role.system:
        raise AppError(403, "role_protected")
    if await session.scalar(select(func.count()).where(User.role == role.slug)):
        raise AppError(409, "role_in_use")
    await session.execute(delete(group_roles).where(group_roles.c.role == role.slug))
    await session.delete(role)
    audit(ROLES_DELETE, target_id=role.slug, target=role.name)
    await session.commit()
    return Response(status_code=204)


async def _user_counts(session: AsyncSession) -> dict[uuid.UUID, int]:
    rows = await session.execute(
        select(user_groups.c.group_id, func.count()).group_by(user_groups.c.group_id)
    )
    return dict(rows.all())


def _group_read(group: Group, users: int) -> GroupRead:
    return GroupRead(
        id=group.id, name=group.name, roles=[role.slug for role in group.roles], users=users
    )


def check_covers_roles(admin: User, roles: Iterable[RoleRecord]) -> None:
    for role in roles:
        check_covers(admin, granted(role))


async def _name_is_free(session: AsyncSession, name: str, group: Group | None = None) -> None:
    other = await session.scalar(select(Group).where(Group.name == name))
    if other is not None and other is not group:
        raise AppError(409, "name_taken")


@access_router.get("/groups")
async def list_groups(session: AsyncSession = Depends(get_async_session)) -> list[GroupRead]:
    counts = await _user_counts(session)
    groups = await session.scalars(select(Group).order_by(Group.name))
    return [_group_read(group, counts.get(group.id, 0)) for group in groups]


@access_router.post("/groups", status_code=201)
async def create_group(
    data: GroupCreate,
    admin: User = manage,
    audit: Audit = Depends(),
    session: AsyncSession = Depends(get_async_session),
) -> GroupRead:
    await _name_is_free(session, data.name)
    roles = await roles_by_slug(session, data.roles)
    check_covers_roles(admin, roles)
    group = Group(name=data.name, roles=roles)
    session.add(group)
    await session.flush()
    audit(
        GROUPS_CREATE,
        target_id=group.id,
        target=group.name,
        changes=diff({}, {"name": group.name, "roles": sorted(role.slug for role in group.roles)}),
    )
    await session.commit()
    return _group_read(group, 0)


async def _editable_group(session: AsyncSession, group_id: uuid.UUID, admin: User) -> Group:
    group = await session.get(Group, group_id)
    if group is None:
        raise AppError(404, "not_found")
    check_covers_roles(admin, group.roles)
    return group


@access_router.put("/groups/{group_id}")
async def update_group(
    group_id: uuid.UUID,
    data: GroupUpdate,
    admin: User = manage,
    audit: Audit = Depends(),
    session: AsyncSession = Depends(get_async_session),
) -> GroupRead:
    group = await _editable_group(session, group_id, admin)
    before = {"name": group.name, "roles": sorted(role.slug for role in group.roles)}
    if data.name is not None and data.name != group.name:
        await _name_is_free(session, data.name, group)
        group.name = data.name
    if data.roles is not None:
        roles = await roles_by_slug(session, data.roles)
        check_covers_roles(admin, roles)
        group.roles = roles
    after = {"name": group.name, "roles": sorted(role.slug for role in group.roles)}
    if changes := diff(before, after):
        audit(GROUPS_UPDATE, target_id=group.id, target=group.name, changes=changes)
    await session.commit()
    return _group_read(group, (await _user_counts(session)).get(group.id, 0))


@access_router.delete("/groups/{group_id}", status_code=204)
async def delete_group(
    group_id: uuid.UUID,
    admin: User = manage,
    audit: Audit = Depends(),
    session: AsyncSession = Depends(get_async_session),
) -> Response:
    group = await _editable_group(session, group_id, admin)
    await session.execute(delete(user_groups).where(user_groups.c.group_id == group.id))
    await session.delete(group)
    audit(GROUPS_DELETE, target_id=group.id, target=group.name)
    await session.commit()
    return Response(status_code=204)
