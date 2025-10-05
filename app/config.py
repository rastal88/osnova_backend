from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

class Settings(BaseSettings):
    HOST: str
    PORT: int
    SECRET_KEY: str
    DEBUG: bool
    DATABASE_URL: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    ALGORITHM: str
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str
    CONFIG_MODE: str

    class Config:
        env_file = ".env"
        extra = "ignore"  # Ignore extra fields in .env

config = Settings()
