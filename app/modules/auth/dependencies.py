from fastapi import Depends
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.modules.auth.backend import fastapi_users
from app.modules.auth.models import RoleRecord, User, group_roles, user_groups
from app.modules.auth.permissions import ADMIN_ACCESS, check_declared
from app.modules.auth.roles import Role

current_user = fastapi_users.current_user(active=True)


def require(*permissions: str):
    """Dependency: the signed-in user has every one of these permissions.

    Returns the user, so it also works as ``user: User = Depends(require(...))``.
    """
    check_declared(*permissions)

    async def permission_checker(user: User = Depends(current_user)) -> User:
        if not user.permissions.issuperset(permissions):
            raise AppError(403, "forbidden")
        return user

    return permission_checker


require_admin = require(ADMIN_ACCESS)


async def users_with_permission(session: AsyncSession, permission: str) -> list[User]:
    """Everyone whose role or group allows the action, e.g. to notify them."""
    check_declared(permission)
    roles = await session.scalars(select(RoleRecord))
    slugs = {role.slug for role in roles if permission in role.permissions} | {Role.ROOT.value}
    through_groups = (
        select(user_groups.c.user_id)
        .join(group_roles, group_roles.c.group_id == user_groups.c.group_id)
        .where(group_roles.c.role.in_(slugs))
    )
    return list(
        await session.scalars(
            select(User).where(or_(User.role.in_(slugs), User.id.in_(through_groups)))
        )
    )
