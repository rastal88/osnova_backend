from typing import Literal

from pydantic import Field

from app.config import config
from app.core.settings import Secret, SettingsGroup


class MailSettings(SettingsGroup):
    """Admin → Settings → Mail: how emails are sent. MAIL_* and SMTP_* in .env are the
    initial values (read when the group has no stored record); the password is stored
    encrypted."""

    group = "mail"

    # "console" writes messages to the log, "smtp" sends them
    backend: Literal["console", "smtp"] = Field(default_factory=lambda: config.MAIL_BACKEND)
    from_address: str = Field(
        default_factory=lambda: config.MAIL_FROM, min_length=3, max_length=254
    )
    smtp_host: str = Field(default_factory=lambda: config.SMTP_HOST, max_length=253)
    smtp_port: int = Field(default_factory=lambda: config.SMTP_PORT, ge=1, le=65535)
    smtp_security: Literal["starttls", "ssl", "none"] = Field(
        default_factory=lambda: config.SMTP_SECURITY
    )
    smtp_username: str = Field(default_factory=lambda: config.SMTP_USERNAME or "", max_length=254)
    smtp_password: Secret = Field(default_factory=lambda: config.SMTP_PASSWORD or "")
    smtp_timeout: int = Field(default_factory=lambda: config.SMTP_TIMEOUT, ge=1, le=120)
