"""Rate limits: a sliding window of hits per key (e.g. a form and a client IP).

A limit is written as "<count>/<period>", e.g. "5/minute" (periods: second,
minute, hour, day); an empty string turns it off. ``LimitFromSetting`` reads the
limit at every hit, so a change in the admin works without a restart.

Where the hits are counted: RATE_LIMIT_STORAGE=memory (default) keeps them in the
process, so with several workers or replicas each one counts on its own;
RATE_LIMIT_STORAGE=redis counts in Redis (REDIS_URL), shared by all of them (needs
requirements/redis.txt). When Redis cannot be reached the request is let through
(fail-open, like the captcha): the process counts in memory meanwhile, tries Redis
again after RETRY_REDIS_SECONDS and logs a warning at most once a minute.
"""

import logging
import math
import time
import uuid
from collections import deque
from collections.abc import Callable
from typing import Annotated

from pydantic import AfterValidator
from pydantic_core import PydanticCustomError
from starlette.requests import Request

from app.config import config
from app.core.errors import AppError

logger = logging.getLogger(__name__)

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


# One atomic step in Redis: drop the hits out of the window, refuse when it is full
# (answering the seconds until the oldest one leaves), otherwise add this hit
_SLIDING_WINDOW = """
local key, now, window, limit = KEYS[1], tonumber(ARGV[1]), tonumber(ARGV[2]), tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
if redis.call('ZCARD', key) >= limit then
  local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
  return math.max(1, math.ceil(tonumber(oldest[2]) + window - now))
end
redis.call('ZADD', key, now, ARGV[4])
redis.call('EXPIRE', key, window)
return 0
"""
# Seconds a Redis request may take before the hit counts as an outage
REDIS_TIMEOUT = 0.5
RETRY_REDIS_SECONDS = 30
WARN_EVERY_SECONDS = 60


class RedisWindow:
    """The sliding window kept in Redis, shared by every process; one per limit."""

    def __init__(self, name: str, client=None):
        self.prefix = f"osnova:rate:{name}:"
        self._client = client
        self._script = None

    def _redis(self):
        if self._client is None:
            # Imported only here: the minimal profile has no Redis client
            import redis.asyncio as redis_asyncio

            self._client = redis_asyncio.from_url(
                config.REDIS_URL,
                socket_timeout=REDIS_TIMEOUT,
                socket_connect_timeout=REDIS_TIMEOUT,
            )
        if self._script is None:
            self._script = self._client.register_script(_SLIDING_WINDOW)
        return self._script

    async def hit(self, key: str, limit: int, window: int) -> int | None:
        """None if allowed, else seconds to wait; raises on a Redis error."""
        args = [time.time(), window, limit, uuid.uuid4().hex]
        retry_after = int(await self._redis()(keys=[self.prefix + key], args=args))
        return retry_after or None


class LimitFromSetting:
    """A rate limit whose value comes from `rule()` (e.g. an admin setting) at every
    hit; the counters start again when the limit changes. `name` keeps the counters of
    each limit apart in Redis."""

    def __init__(self, rule: Callable[[], str], name: str = "default"):
        self.rule = rule
        self.name = name
        self.current: str | None = None
        self.parsed: tuple[int, int] | None = None
        self.limiter: RateLimiter | None = None
        self.redis: RedisWindow | None = None
        self.redis_down_until = 0.0
        self.warned_at = -WARN_EVERY_SECONDS

    @property
    def hits(self) -> dict[str, deque[float]]:
        return self.limiter.hits if self.limiter else {}

    def _refresh(self) -> None:
        value = self.rule()
        if value != self.current:
            self.parsed = parse_limit(value)
            self.limiter = RateLimiter(*self.parsed) if self.parsed else None
            self.current = value

    async def hit(self, key: str) -> int | None:
        """None if allowed, else seconds until the next hit is."""
        self._refresh()
        if self.parsed is None or self.limiter is None:
            return None
        now = time.monotonic()
        if config.RATE_LIMIT_STORAGE == "redis" and now >= self.redis_down_until:
            if self.redis is None:
                self.redis = RedisWindow(self.name)
            try:
                return await self.redis.hit(key, *self.parsed)
            except Exception:
                # Fail-open: the request goes on, this process counts on its own for now
                self.redis_down_until = now + RETRY_REDIS_SECONDS
                if now - self.warned_at >= WARN_EVERY_SECONDS:
                    self.warned_at = now
                    logger.warning(
                        "Rate limits: Redis is unreachable, counting in this process",
                        exc_info=True,
                    )
        return self.limiter.hit(key)


def check_rate_limit_config() -> None:
    """At start: counting in Redis needs its address and its client."""
    if config.RATE_LIMIT_STORAGE != "redis":
        return
    if not config.REDIS_URL:
        raise RuntimeError("RATE_LIMIT_STORAGE=redis requires REDIS_URL")
    try:
        import redis.asyncio  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "RATE_LIMIT_STORAGE=redis requires the Redis client: requirements/redis.txt"
        ) from exc


def client_address(request: Request) -> str:
    # Behind a proxy the client address is correct only with uvicorn
    # --proxy-headers and FORWARDED_ALLOW_IPS set to the proxy address
    return request.client.host if request.client else "unknown"


async def check_limit(limiter: RateLimiter | LimitFromSetting | None, key: str) -> None:
    """Count a hit for `key`; over the limit raises 429 with Retry-After."""
    if limiter is None:
        return
    if isinstance(limiter, LimitFromSetting):
        retry_after = await limiter.hit(key)
    else:
        retry_after = limiter.hit(key)
    if retry_after is not None:
        raise AppError(429, "too_many_requests", headers={"Retry-After": str(retry_after)})
