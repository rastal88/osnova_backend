"""Optional captcha for public forms and sign-up, next to the honeypot and rate limits.

Off by default. Set CAPTCHA_PROVIDER ("turnstile": Cloudflare Turnstile) with
CAPTCHA_SITE_KEY and CAPTCHA_SECRET_KEY to turn it on; the owner can switch it off
and on again in the admin (Admin → Settings → Protection). The frontend learns the
provider and the site key from /bootstrap, shows the widget and sends its token in
the X-Captcha-Token header; ``require_captcha`` checks it on the server (standard
library only). Protect another endpoint with ``Depends(require_captcha)``.

A token the provider refuses is an error for the visitor. When the provider cannot
be reached the request is let through with a warning: an outage on their side must
not stop every form of the site, and the other protections still work.

Another provider: a function ``(secret, token) -> bool`` in PROVIDERS (raise
OSError when the service is unreachable) and its widget on the frontend.
"""

import json
import logging
import urllib.parse
import urllib.request
from collections.abc import Callable

from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from pydantic import Field, field_validator
from pydantic_core import PydanticCustomError

from app.config import Settings, config
from app.core.errors import AppError
from app.core.settings import SettingsGroup, settings

logger = logging.getLogger(__name__)

HEADER = "X-Captcha-Token"
# Seconds: when the provider is down, the visitor waits this long before being let through
TIMEOUT = 3
# Turnstile tokens are up to 2048 characters
MAX_TOKEN_LENGTH = 2048
TURNSTILE_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

Verifier = Callable[[str, str], bool]


def _turnstile(secret: str, token: str) -> bool:
    # The visitor's IP is optional for Turnstile and is not sent
    body = urllib.parse.urlencode({"secret": secret, "response": token}).encode()
    with urllib.request.urlopen(TURNSTILE_URL, data=body, timeout=TIMEOUT) as response:
        result = json.load(response)
    if not result.get("success"):
        codes = result.get("error-codes") or []
        # A wrong secret refuses every visitor: make it visible
        level = logging.ERROR if "invalid-input-secret" in codes else logging.INFO
        logger.log(level, "Captcha refused: %s", ", ".join(codes) or "no reason given")
    return bool(result.get("success"))


PROVIDERS: dict[str, Verifier] = {"turnstile": _turnstile}


def captcha_configured(values: Settings = config) -> bool:
    return bool(values.CAPTCHA_PROVIDER and values.CAPTCHA_SITE_KEY and values.CAPTCHA_SECRET_KEY)


class ProtectionSettings(SettingsGroup):
    group = "protection"

    # On as soon as the keys are set; the owner can switch it off without a restart
    captcha: bool = Field(default_factory=captcha_configured)

    @field_validator("captcha")
    @classmethod
    def _needs_keys(cls, value: bool) -> bool:
        if value and not captcha_configured():
            raise PydanticCustomError("captcha_not_configured", "Captcha keys are not set")
        return value


def captcha_active() -> bool:
    """Configured in .env and not switched off in the admin."""
    return captcha_configured() and settings.get(ProtectionSettings).captcha


def check_captcha_config() -> None:
    """At start: a provider without its keys protects nothing."""
    if config.CAPTCHA_PROVIDER and not captcha_configured():
        logger.warning(
            "CAPTCHA_PROVIDER=%s, but CAPTCHA_SITE_KEY or CAPTCHA_SECRET_KEY is not set: "
            "the captcha is off.",
            config.CAPTCHA_PROVIDER,
        )


async def require_captcha(request: Request) -> None:
    """Dependency (or a direct call): the request must carry a token the provider accepts."""
    if not captcha_active():
        return
    token = request.headers.get(HEADER, "").strip()
    if not token or len(token) > MAX_TOKEN_LENGTH:
        raise AppError(400, "captcha_failed")
    verify = PROVIDERS[config.CAPTCHA_PROVIDER]
    try:
        accepted = await run_in_threadpool(verify, config.CAPTCHA_SECRET_KEY or "", token)
    except (OSError, ValueError):
        logger.warning("Captcha provider is unreachable, request let through", exc_info=True)
        return
    if not accepted:
        raise AppError(400, "captcha_failed")
