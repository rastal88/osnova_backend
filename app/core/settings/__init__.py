"""Settings the site owner changes at runtime (in the admin).

A group of settings is a Pydantic model (SettingsGroup) with defaults, usually
taken from .env (app/config.py). The project's groups are listed in
app/settings.py. Code reads them typed, from memory:

    from app.core.settings import settings
    settings.get(SiteSettings).contact_email

Without the settings module (minimal profile, or no admin) the defaults are
used. With it, values are stored in the database and loaded into ``settings``
(app/modules/settings). The admin form is described by
app/core/settings/schema.py.
"""

from app.core.settings.base import OptionalEmail, OptionalPhone, SettingsGroup
from app.core.settings.store import SettingsStore, settings

__all__ = ["OptionalEmail", "OptionalPhone", "SettingsGroup", "SettingsStore", "settings"]
