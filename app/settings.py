"""Settings of this project that the owner edits in the admin (Admin → Settings).

Each group is a SettingsGroup with defaults (usually from .env); add a group to
GROUPS and its texts to the "settings" section of app/core/locales/*.json. Read
values anywhere with ``settings.get(SiteSettings).name``. Infrastructure,
secrets and capability flags stay in .env (app/config.py): they need a restart.
"""

from pydantic import Field

from app.config import config
from app.core.captcha import ProtectionSettings
from app.core.languages import LanguageSettings
from app.core.settings import OptionalEmail, OptionalPhone, SettingsGroup


class SiteSettings(SettingsGroup):
    group = "site"

    name: str = Field(default=config.APP_NAME, min_length=1, max_length=100)
    contact_email: OptionalEmail = ""
    contact_phone: OptionalPhone = ""


GROUPS: tuple[type[SettingsGroup], ...] = (SiteSettings, LanguageSettings, ProtectionSettings)
