"""In-memory rate limits, no extra dependencies.

A limit is written as "<count>/<period>", e.g. "5/minute" (periods: second,
minute, hour, day); an empty string turns it off. Counters live in the process,
so with several workers each one counts on its own — a shared store (Redis)
is the next step for the scalable profile. ``LimitFromSetting`` reads the limit at
every hit, so a change in the admin works without a restart.
"""

import math
import time
from collections import deque
from collections.abc import Callable
from typing import Annotated

from pydantic import AfterValidator
from pydantic_core import PydanticCustomError
from starlette.requests import Request

from app.core.errors import AppError

PERIODS: dict[str, int] = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}
# Keys whose hits have all expired are dropped once there are this many
CLEANUP_AT = 10_000


def parse_limit(value: str) -> tuple[int, int] | None:
    """ "5/minute" -> (5, 60); "" -> None."""
    value = value.strip()
    if not value:
        return None
    count, _, period = value.partition("/")
    try:
        limit = int(count)
    except ValueError:
        limit = 0
    if limit < 1 or period.strip() not in PERIODS:
        raise ValueError(f"Invalid rate limit {value!r}, expected e.g. '5/minute'")
    return limit, PERIODS[period.strip()]


class RateLimiter:
    """Sliding window: at most `limit` hits per `window` seconds for each key."""

    def __init__(self, limit: int, window: int):
        self.limit = limit
        self.window = window
        self.hits: dict[str, deque[float]] = {}

    def hit(self, key: str) -> int | None:
        """Count a hit; returns None if allowed, else seconds until the next one is."""
        now = time.monotonic()
        if len(self.hits) >= CLEANUP_AT:
            self._cleanup(now)

        hits = self.hits.setdefault(key, deque())
        while hits and hits[0] <= now - self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return max(1, math.ceil(hits[0] + self.window - now))
        hits.append(now)
        return None

    def _cleanup(self, now: float):
        for key in [key for key, hits in self.hits.items() if hits[-1] <= now - self.window]:
            del self.hits[key]


def _valid_limit(value: str) -> str:
    try:
        parse_limit(value)
    except ValueError:
        raise PydanticCustomError("rate_limit_invalid", "Expected e.g. 5/minute") from None
    return value.strip()


# A settings field: "5/minute", or empty for no limit
RateLimit = Annotated[str, AfterValidator(_valid_limit)]


class LimitFromSetting:
    """A RateLimiter whose limit comes from `rule()` (e.g. an admin setting) at every hit;
    the counters start again when the limit changes."""

    def __init__(self, rule: Callable[[], str]):
        self.rule = rule
        self.current: str | None = None
        self.limiter: RateLimiter | None = None

    @property
    def hits(self) -> dict[str, deque[float]]:
        return self.limiter.hits if self.limiter else {}

    def hit(self, key: str) -> int | None:
        value = self.rule()
        if value != self.current:
            parsed = parse_limit(value)
            self.limiter = RateLimiter(*parsed) if parsed else None
            self.current = value
        return self.limiter.hit(key) if self.limiter else None


def client_address(request: Request) -> str:
    # Behind a proxy the client address is correct only with uvicorn
    # --proxy-headers and FORWARDED_ALLOW_IPS set to the proxy address
    return request.client.host if request.client else "unknown"


def check_limit(limiter: RateLimiter | LimitFromSetting | None, key: str) -> None:
    """Count a hit for `key`; over the limit raises 429 with Retry-After."""
    if limiter is None:
        return
    retry_after = limiter.hit(key)
    if retry_after is not None:
        raise AppError(429, "too_many_requests", headers={"Retry-After": str(retry_after)})
