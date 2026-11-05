from app.config import config
from app.core.capabilities import capabilities


def get_bootstrap_config() -> dict:
    return {
        "application": {
            "name": config.APP_NAME,
            "version": config.APP_VERSION,
        },
        "profile": config.APP_PROFILE,
        "features": {
            "authentication": capabilities.authentication,
            "admin": capabilities.admin,
            "files": capabilities.files,
            "notifications": capabilities.notifications,
            "background_tasks": capabilities.background_tasks,
        },
    }
