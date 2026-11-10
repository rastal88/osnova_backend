from fastapi import Depends, Request

from app.config import config
from app.core.rate_limit import RateLimiter, check_limit, client_address, parse_limit

rate_limit = parse_limit(config.AUTH_RATE_LIMIT)
limiter = RateLimiter(*rate_limit) if rate_limit else None


async def limit_by_ip(request: Request) -> None:
    """Slows down password guessing and sending emails to someone else's address."""
    check_limit(limiter, f"{request.url.path}:{client_address(request)}")


limited = [Depends(limit_by_ip)]
