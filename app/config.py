from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Osnova Application"
    APP_VERSION: str = "0.1.0"
    APP_PROFILE: Literal["minimal", "standard", "scalable"] = "minimal"
    APP_HOST: str = "localhost"
    APP_PORT: int = 8000
    DEBUG: bool = False

    # Capabilities: each flag turns on a module from app/modules (see app/core/modules.py)
    AUTH_ENABLED: bool = False
    ADMIN_ENABLED: bool = False
    FILES_ENABLED: bool = False
    NOTIFICATIONS_ENABLED: bool = False
    BACKGROUND_TASKS_ENABLED: bool = False

    CORS_ORIGINS: str = "http://localhost:5173"

    # Database module: enabled when DATABASE_URL is set
    DATABASE_URL: str | None = None
    DB_ECHO: bool = False

    # Auth module
    SECRET_KEY: str | None = None
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    AUTH_STRATEGY: Literal["jwt", "redis"] = "jwt"
    COOKIE_SECURE: bool = False

    REDIS_URL: str | None = None

    # Files module
    FILES_DIR: str = "uploads"
    FILES_MAX_SIZE_MB: int = 10

    # Background tasks module
    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


config = get_settings()
