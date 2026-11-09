"""APP_PROFILE check: warns at start when the profile does not match the setup."""

import logging

logger = logging.getLogger(__name__)


def profile_warnings(profile: str, modules: list[str]) -> list[str]:
    if profile == "minimal":
        if modules:
            return [
                f"APP_PROFILE=minimal, but optional modules are enabled: {', '.join(modules)}. "
                "Set APP_PROFILE=standard or turn them off (DATABASE_URL, *_ENABLED)."
            ]
        return []
    if "db" not in modules:
        return [
            f"APP_PROFILE={profile}, but DATABASE_URL is not set: "
            "the database and the modules that need it are off."
        ]
    return []


def check_profile(profile: str, modules: list[str]) -> None:
    for warning in profile_warnings(profile, modules):
        logger.warning(warning)
