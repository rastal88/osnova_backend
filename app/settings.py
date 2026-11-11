"""Settings of this project that the owner edits in the admin (Admin → Settings).

Each group is a SettingsGroup with defaults (usually from .env); add a group to
GROUPS and its texts to the "settings" section of app/core/locales/*.json. Read
values anywhere with ``settings.get(SiteSettings).name``. A group of an optional
module lives in its ``settings.py`` (``GROUPS``) and is shown only with the module.
Editing a group needs the permission ``settings.<group>``. Infrastructure, secrets
needed to start and capability flags stay in .env (app/config.py): they need a
restart.
"""

from pydantic import Field

from app.config import config
from app.core.captcha import ProtectionSettings
from app.core.languages import LanguageSettings
from app.core.mail.settings import MailSettings
from app.core.settings import OptionalEmail, OptionalPhone, SettingsGroup

# Days are capped at ten years
MAX_DAYS = 3650


class SiteSettings(SettingsGroup):
    group = "site"

    name: str = Field(default=config.APP_NAME, min_length=1, max_length=100)
    contact_email: OptionalEmail = ""
    contact_phone: OptionalPhone = ""


class RetentionSettings(SettingsGroup):
    """How long old data is kept; the nightly cleanup removes the rest (0: keep it)."""

    group = "retention"

    notifications_days: int = Field(
        default_factory=lambda: config.NOTIFICATIONS_KEEP_DAYS, ge=0, le=MAX_DAYS
    )
    unverified_account_days: int = Field(
        default_factory=lambda: config.UNVERIFIED_ACCOUNT_DAYS, ge=0, le=MAX_DAYS
    )
    audit_days: int = Field(default_factory=lambda: config.AUDIT_KEEP_DAYS, ge=0, le=MAX_DAYS)


GROUPS: tuple[type[SettingsGroup], ...] = (
    SiteSettings,
    LanguageSettings,
    MailSettings,
    ProtectionSettings,
    RetentionSettings,
)
