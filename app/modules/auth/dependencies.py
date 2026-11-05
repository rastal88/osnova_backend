from fastapi import Depends, HTTPException, status

from app.modules.auth.backend import fastapi_users
from app.modules.auth.models import User
from app.modules.auth.roles import Role

current_user = fastapi_users.current_user(active=True)


def require_role(required_role: Role):
    async def role_checker(user: User = Depends(current_user)):
        if user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {required_role.value}",
            )
        return user

    return role_checker


def require_any_role(*roles: Role):
    async def role_checker(user: User = Depends(current_user)):
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required one of roles: {[r.value for r in roles]}",
            )
        return user

    return role_checker
