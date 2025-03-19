from fastapi_users.authentication import JWTAuthentication
from app.config import config

jwt_authentication = JWTAuthentication(
    secret=config.SECRET_KEY,
    lifetime_seconds=3600,
    tokenUrl="/auth/jwt/login",
)
