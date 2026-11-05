from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str
    APP_VERSION: str
    APP_PROFILE: str
    APP_HOST: str
    APP_PORT: int
    DEBUG: bool

    DATABASE_URL: str | None = None

    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    COOKIE_SECURE: bool = False

    REDIS_URL: str | None = None
    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None

    AUTH_ENABLED: bool
    ADMIN_ENABLED: bool
    FILES_ENABLED: bool
    NOTIFICATIONS_ENABLED: bool
    BACKGROUND_TASKS_ENABLED: bool

    CORS_ORIGINS: str = "http://localhost:5173"

    OAUTH2_CLIENT_ID: str | None = None
    OAUTH2_CLIENT_SECRET: str | None = None
    OAUTH2_REDIRECT_URI: str | None = None

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
