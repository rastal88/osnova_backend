from dataclasses import dataclass

from app.config import Settings, config


@dataclass(frozen=True)
class Capabilities:
    authentication: bool
    admin: bool
    files: bool
    notifications: bool
    background_tasks: bool


capabilities = Capabilities(
    authentication=config.AUTH_ENABLED,
    admin=config.ADMIN_ENABLED,
    files=config.FILES_ENABLED,
    notifications=config.NOTIFICATIONS_ENABLED,
    background_tasks=config.BACKGROUND_TASKS_ENABLED,
)


def oauth_providers(settings: Settings) -> list[str]:
    """Sign-in providers whose keys are set (the auth module must be on)."""
    if not settings.AUTH_ENABLED:
        return []
    keys = {"google": (settings.GOOGLE_CLIENT_ID, settings.GOOGLE_CLIENT_SECRET)}
    return [name for name, values in keys.items() if all(values)]
