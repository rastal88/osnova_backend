"""APP_PROFILE check: warns at start when the profile does not match the setup."""

import logging

logger = logging.getLogger(__name__)


def profile_warnings(profile: str, modules: list[str], rate_limits: str = "memory") -> list[str]:
    if profile == "minimal":
        if modules:
            return [
                f"APP_PROFILE=minimal, but optional modules are enabled: {', '.join(modules)}. "
                "Set APP_PROFILE=standard or turn them off (DATABASE_URL, *_ENABLED)."
            ]
        return []
    warnings = []
    if "db" not in modules:
        warnings.append(
            f"APP_PROFILE={profile}, but DATABASE_URL is not set: "
            "the database and the modules that need it are off."
        )
    if profile == "scalable" and rate_limits != "redis":
        warnings.append(
            "APP_PROFILE=scalable, but rate limits count in each replica: "
            "set RATE_LIMIT_STORAGE=redis to share them."
        )
    return warnings


def check_profile(profile: str, modules: list[str], rate_limits: str = "memory") -> None:
    for warning in profile_warnings(profile, modules, rate_limits):
        logger.warning(warning)
