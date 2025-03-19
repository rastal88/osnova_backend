from fastapi import HTTPException, status
from app.core.roles import Role, PERMISSIONS

def check_permission(user_role: Role, required_permission: str):
    """Проверяет, есть ли у пользователя необходимое право."""
    if required_permission not in PERMISSIONS.get(user_role, []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action.",
        )