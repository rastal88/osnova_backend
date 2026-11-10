from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.version import VERSION


class Settings(BaseSettings):
    APP_NAME: str = "Osnova Application"
    # The release of this code (app/version.py); set in .env only to override it
    APP_VERSION: str = VERSION
    APP_PROFILE: Literal["minimal", "standard", "scalable"] = "minimal"
    APP_HOST: str = "localhost"
    APP_PORT: int = 8000
    # Development mode: serves /docs, /redoc and /openapi.json
    DEBUG: bool = False

    # Capabilities: each flag turns on a module from app/modules (see app/core/modules.py)
    AUTH_ENABLED: bool = False
    ADMIN_ENABLED: bool = False
    FILES_ENABLED: bool = False
    NOTIFICATIONS_ENABLED: bool = False
    BACKGROUND_TASKS_ENABLED: bool = False

    # Interface languages: comma-separated codes from app/core/languages.py
    LANGUAGES: str = "en,ru"
    DEFAULT_LANGUAGE: str = "en"

    CORS_ORIGINS: str = "http://localhost:5173"

    # Forms (app/forms.py): "log" writes submissions to the log, "file" also to FORMS_FILE
    FORMS_DELIVERY: Literal["log", "file"] = "log"
    FORMS_FILE: str = "data/forms.jsonl"
    # Submissions per client IP and form, e.g. "5/minute" (empty: no limit)
    FORMS_RATE_LIMIT: str = "5/minute"

    # Database module: enabled when DATABASE_URL is set
    DATABASE_URL: str | None = None
    DB_ECHO: bool = False

    # Auth module
    SECRET_KEY: str | None = None
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    AUTH_STRATEGY: Literal["jwt", "redis"] = "jwt"
    COOKIE_SECURE: bool = False
    # Requests per client IP to each of sign-in, sign-up, password reset and email
    # confirmation, e.g. "10/minute" (empty: no limit)
    AUTH_RATE_LIMIT: str = "10/minute"
    # Sign-in with Google: both set turns it on. Authorized redirect URI in Google Cloud:
    # <FRONTEND_URL>/oauth/google/callback
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None

    REDIS_URL: str | None = None

    # Public address of the frontend: links in emails (verification, password reset)
    FRONTEND_URL: str = "http://localhost:5173"

    # Email (app/core/mail): "console" writes messages to the log, "smtp" sends them
    MAIL_BACKEND: Literal["console", "smtp"] = "console"
    MAIL_FROM: str = "Osnova <noreply@example.com>"
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_SECURITY: Literal["starttls", "ssl", "none"] = "starttls"
    SMTP_TIMEOUT: int = 10

    # Notifications module: where notifications go besides the bell, e.g. "in_app,email"
    NOTIFICATIONS_CHANNELS: str = "in_app"

    # Settings module: seconds before a process reloads settings changed in the admin
    SETTINGS_REFRESH_SECONDS: int = 30

    # Files module: "local" keeps files in FILES_DIR, "s3" in an S3-compatible bucket
    FILES_STORAGE: Literal["local", "s3"] = "local"
    FILES_DIR: str = "uploads"
    FILES_MAX_SIZE_MB: int = 10
    # Comma-separated MIME types or prefixes ("image/", "application/pdf"); empty: any
    FILES_ALLOWED_TYPES: str = ""
    S3_ENDPOINT_URL: str | None = None
    S3_BUCKET: str | None = None
    S3_REGION: str = "us-east-1"
    S3_ACCESS_KEY: str | None = None
    S3_SECRET_KEY: str | None = None
    # Lifetime of download links to the bucket
    S3_LINK_SECONDS: int = 300

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
