import logging
import os
import uuid

import pytest

from app.config import config
from app.core import rate_limit
from app.core.rate_limit import (
    LimitFromSetting,
    RateLimiter,
    RedisWindow,
    check_rate_limit_config,
    parse_limit,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("5/minute", (5, 60)), (" 10/hour ", (10, 3600)), ("1/second", (1, 1)), ("", None)],
)
def test_parse_limit(value, expected):
    assert parse_limit(value) == expected


@pytest.mark.parametrize("value", ["5", "five/minute", "0/minute", "5/week"])
def test_parse_invalid_limit(value):
    with pytest.raises(ValueError):
        parse_limit(value)


def test_sliding_window(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: now[0])
    limiter = RateLimiter(2, 60)

    assert limiter.hit("a") is None
    now[0] += 10
    assert limiter.hit("a") is None
    assert limiter.hit("a") == 50
    assert limiter.hit("b") is None

    now[0] += 50
    assert limiter.hit("a") is None
    assert limiter.hit("a") == 10


def test_expired_keys_are_cleaned(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(rate_limit, "CLEANUP_AT", 3)
    limiter = RateLimiter(1, 60)

    for key in "abc":
        limiter.hit(key)
    now[0] += 61
    limiter.hit("d")
    assert list(limiter.hits) == ["d"]


class _BrokenRedis:
    """A Redis client whose every call fails, like a server that is down."""

    calls = 0

    def register_script(self, script):
        async def run(keys, args):
            _BrokenRedis.calls += 1
            raise ConnectionError("Redis is down")

        return run


@pytest.mark.anyio
async def test_a_setting_limit_counts_in_memory(monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_STORAGE", "memory")
    rule = {"value": "2/minute"}
    limiter = LimitFromSetting(lambda: rule["value"], "test")
    assert await limiter.hit("a") is None
    assert await limiter.hit("a") is None
    assert await limiter.hit("a") is not None
    # A new value starts again; empty turns it off
    rule["value"] = "3/minute"
    assert await limiter.hit("a") is None
    rule["value"] = ""
    assert all([await limiter.hit("a") is None for _ in range(10)])


@pytest.mark.anyio
async def test_redis_outage_lets_requests_through(monkeypatch, caplog):
    """Fail-open: the process counts in memory meanwhile and tries Redis again later."""
    monkeypatch.setattr(config, "RATE_LIMIT_STORAGE", "redis")
    limiter = LimitFromSetting(lambda: "2/minute", "test")
    limiter.redis = RedisWindow("test", client=_BrokenRedis())
    _BrokenRedis.calls = 0

    with caplog.at_level(logging.WARNING, logger="app.core.rate_limit"):
        assert await limiter.hit("a") is None
        assert await limiter.hit("a") is None
        # Still limited, by the counters of this process
        assert await limiter.hit("a") is not None
    assert _BrokenRedis.calls == 1
    assert caplog.text.count("Redis is unreachable") == 1

    # After the pause Redis is asked again
    monkeypatch.setattr(limiter, "redis_down_until", 0.0)
    await limiter.hit("b")
    assert _BrokenRedis.calls == 2


def test_redis_storage_needs_its_address(monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_STORAGE", "redis")
    monkeypatch.setattr(config, "REDIS_URL", None)
    with pytest.raises(RuntimeError, match="REDIS_URL"):
        check_rate_limit_config()
    monkeypatch.setattr(config, "RATE_LIMIT_STORAGE", "memory")
    check_rate_limit_config()


@pytest.mark.modules("files")
def test_scalable_refuses_local_files(monkeypatch):
    from fastapi import FastAPI

    from app.modules import files

    monkeypatch.setattr(config, "APP_PROFILE", "scalable")
    monkeypatch.setattr(config, "FILES_STORAGE", "local")
    with pytest.raises(RuntimeError, match="FILES_STORAGE=s3"):
        files.register(FastAPI())


# A real Redis, e.g. in CI: TEST_REDIS_URL=redis://localhost:6379/15 (the keys are removed)
TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL")


@pytest.mark.anyio
@pytest.mark.skipif(not TEST_REDIS_URL, reason="TEST_REDIS_URL is not set")
async def test_replicas_share_the_count_in_redis(monkeypatch):
    import redis.asyncio as redis_asyncio

    monkeypatch.setattr(config, "RATE_LIMIT_STORAGE", "redis")
    client = redis_asyncio.from_url(TEST_REDIS_URL)
    name = f"test-{uuid.uuid4().hex}"
    # Two processes, as two replicas behind a load balancer
    first, second = (LimitFromSetting(lambda: "3/minute", name) for _ in range(2))
    first.redis = RedisWindow(name, client=client)
    second.redis = RedisWindow(name, client=client)
    try:
        assert await first.hit("ip") is None
        assert await second.hit("ip") is None
        assert await first.hit("ip") is None
        retry_after = await second.hit("ip")
        assert retry_after is not None and 1 <= retry_after <= 60
        # Another key has its own window
        assert await second.hit("other") is None
        assert await client.ttl(f"osnova:rate:{name}:ip") > 0
    finally:
        await client.delete(f"osnova:rate:{name}:ip", f"osnova:rate:{name}:other")
        await client.aclose()
