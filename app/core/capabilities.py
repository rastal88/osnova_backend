from dataclasses import dataclass
from app.config import config


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