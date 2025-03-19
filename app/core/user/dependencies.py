from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.config import config
from app.core.database import SessionLocal
from app.models.user import User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/jwt/login")

async def get_user_db():
    async with SessionLocal() as session:
        yield SQLAlchemyUserDatabase(session, User)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    print(2134234)
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    async with SessionLocal() as session:
        user = await session.query(User).filter(User.email == email).first()
        if user is None:
            raise credentials_exception
        return user

async def get_current_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this resource.",
        )
    return current_user