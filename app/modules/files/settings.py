from pydantic import Field

from app.config import config
from app.core.settings import SettingsGroup


class FilesSettings(SettingsGroup):
    """Admin → Settings → Files; FILES_MAX_SIZE_MB and FILES_ALLOWED_TYPES in .env are the
    initial values. Behind nginx a request is also limited by client_max_body_size."""

    group = "files"

    max_size_mb: int = Field(default_factory=lambda: config.FILES_MAX_SIZE_MB, ge=1, le=1024)
    # Comma-separated MIME types or prefixes ("image/", "application/pdf"); empty: any
    allowed_types: str = Field(default_factory=lambda: config.FILES_ALLOWED_TYPES, max_length=500)

    @property
    def allowed(self) -> tuple[str, ...]:
        return tuple(item.strip() for item in self.allowed_types.split(",") if item.strip())


GROUPS = (FilesSettings,)
