from app.config import config
from app.core.capabilities import capabilities
from app.core.languages import languages


def get_bootstrap_config() -> dict:
    return {
        "application": {
            "name": config.APP_NAME,
            "version": config.APP_VERSION,
        },
        "profile": config.APP_PROFILE,
        "i18n": {
            "languages": [{"code": lang.code, "name": lang.name} for lang in languages.enabled],
            "default": languages.default,
        },
        "features": {
            "authentication": capabilities.authentication,
            "admin": capabilities.admin,
            "files": capabilities.files,
            "notifications": capabilities.notifications,
            "background_tasks": capabilities.background_tasks,
        },
    }
