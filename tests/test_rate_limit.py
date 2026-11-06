import pytest

from app.core import rate_limit
from app.core.rate_limit import RateLimiter, parse_limit


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
