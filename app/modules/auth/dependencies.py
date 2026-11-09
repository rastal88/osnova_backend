from fastapi import Depends

from app.core.errors import AppError
from app.modules.auth.backend import fastapi_users
from app.modules.auth.models import User
from app.modules.auth.roles import ADMIN_ROLES, Role

current_user = fastapi_users.current_user(active=True)


def require_any_role(*roles: Role):
    async def role_checker(user: User = Depends(current_user)):
        if user.role not in roles:
            raise AppError(403, "forbidden")
        return user

    return role_checker


require_admin = require_any_role(*ADMIN_ROLES)
