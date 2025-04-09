from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.roles import Role, PERMISSIONS
from app.core.user.utils import UserManager, get_user_manager
from app.core.user.strategies import auth_backend

security = HTTPBearer()

async def get_current_user_role(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user_manager: UserManager = Depends(get_user_manager)
) -> Role:
    try:
        user_id = auth_backend.get_strategy().get_token_id(credentials.credentials)
        user = await user_manager.get(user_id)
        return user.role
    except Exception:
        raise HTTPException(status_code=403, detail="Invalid token or permissions")


def has_permission(required_permission: str):
    async def permission_checker(role: Role = Depends(get_current_user_role)):
        if required_permission not in PERMISSIONS.get(role, []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
    return Depends(permission_checker)