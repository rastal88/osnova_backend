from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):

    DATABASE_URL: str = Field(..., env="DATABASE_URL")

    SECRET_KEY: str = Field(..., env="SECRET_KEY")
    DEBUG: bool = Field(False, env="DEBUG")
    CONFIG_MODE: str = Field("PRODUCTION", env="CONFIG_MODE")

    CELERY_BROKER_URL: str = Field("redis://localhost:6379/0", env="CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND: str = Field("redis://localhost:6379/0", env="CELERY_RESULT_BACKEND")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


# Функция для получения настроек
def get_settings():
    return Settings()

settings = get_settings()