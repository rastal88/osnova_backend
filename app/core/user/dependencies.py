from authlib.jose import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

from app.config import config
from app.core.roles import Role
from app.core.user.utils import UserManager, get_user_manager
from app.core.user.strategies import fastapi_users
from app.models.user import User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/jwt/login")
current_user = fastapi_users.current_user()

def require_role(required_role: Role):
    async def role_checker(user: User = Depends(current_user)):
        if user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {required_role}",
            )
        return user
    return role_checker

def require_any_role(*roles: Role):
    async def role_checker(user: User = Depends(current_user)):
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required one of roles: {roles}",
            )
        return user
    return role_checker


async def get_current_admin(
    user: User = Depends(fastapi_users.current_user(active=True, superuser=True))
) -> User:
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges"
        )
    return user

async def get_current_user(
        token: str = Depends(oauth2_scheme),
        user_manager: UserManager = Depends(get_user_manager),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await user_manager.get(user_id)
    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(
        current_user: User = Depends(get_current_user),
):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user