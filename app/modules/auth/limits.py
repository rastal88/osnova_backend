from fastapi import Depends, Request

from app.config import config
from app.core.captcha import ProtectionSettings
from app.core.rate_limit import LimitFromSetting, check_limit, client_address, parse_limit
from app.core.settings import settings

# A wrong value in .env stops the start; later the limit comes from the admin
parse_limit(config.AUTH_RATE_LIMIT)
limiter = LimitFromSetting(lambda: settings.get(ProtectionSettings).auth_rate_limit)


async def limit_by_ip(request: Request) -> None:
    """Slows down password guessing and sending emails to someone else's address."""
    check_limit(limiter, f"{request.url.path}:{client_address(request)}")


limited = [Depends(limit_by_ip)]
