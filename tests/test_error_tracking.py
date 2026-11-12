"""Error tracking: off without SENTRY_DSN; with it, errors are sent without personal data."""

import logging
import sys

import pytest
import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sentry_sdk.transport import Transport

from app.config import config
from app.core.error_tracking import setup_error_tracking


class Captured(Transport):
    """Keeps the events instead of sending them."""

    def __init__(self, options=None):
        super().__init__(options)
        self.events: list[dict] = []

    def capture_envelope(self, envelope) -> None:
        event = envelope.get_event()
        if event is not None:
            self.events.append(event)


@pytest.fixture
def sentry(monkeypatch):
    """setup_error_tracking() with a DSN, events kept in a list."""
    transport = Captured()
    real_init = sentry_sdk.init
    monkeypatch.setattr(config, "SENTRY_DSN", "https://public@sentry.example.invalid/1")
    monkeypatch.setattr(sentry_sdk, "init", lambda **kw: real_init(transport=transport, **kw))
    setup_error_tracking()
    yield transport.events
    sentry_sdk.get_client().close()
    real_init(dsn=None)


def _app() -> FastAPI:
    app = FastAPI()

    @app.post("/boom")
    async def boom(request: Request):
        password = (await request.json())["password"]  # noqa: F841 - a local to be left out
        raise RuntimeError("boom")

    return app


def test_off_without_dsn(monkeypatch):
    monkeypatch.setattr(config, "SENTRY_DSN", "")
    monkeypatch.setitem(sys.modules, "sentry_sdk", None)
    setup_error_tracking()  # does not even import sentry_sdk


def test_dsn_without_the_package_stops_the_app(monkeypatch):
    monkeypatch.setattr(config, "SENTRY_DSN", "https://public@sentry.example.invalid/1")
    monkeypatch.setitem(sys.modules, "sentry_sdk", None)
    with pytest.raises(RuntimeError, match="requirements/sentry.txt"):
        setup_error_tracking()


def test_an_api_error_is_sent_without_personal_data(sentry):
    client = TestClient(_app(), raise_server_exceptions=False)
    response = client.post(
        "/boom?page=2",
        json={"password": "hunter2-secret", "email": "ann@example.com"},
        headers={"Authorization": "Bearer token-value", "X-Forwarded-For": "203.0.113.7"},
        cookies={"session": "cookie-value"},
    )
    assert response.status_code == 500
    sentry_sdk.flush()

    errors = [event for event in sentry if event.get("exception")]
    assert errors, "the error reached Sentry"
    event = errors[0]
    assert event["exception"]["values"][-1]["value"] == "boom"
    assert event["release"] == f"osnova-backend@{config.APP_VERSION}"
    assert event["environment"] == config.SENTRY_ENVIRONMENT
    text = repr(event)
    for secret in (
        "hunter2-secret",
        "ann@example.com",
        "token-value",
        "cookie-value",
        "203.0.113.7",
    ):
        assert secret not in text
    assert "ip_address" not in event.get("user", {})


def test_error_lines_are_events_and_info_lines_are_not_kept(sentry):
    logger = logging.getLogger("app.test.sentry")
    logger.info("Form submitted: ann@example.com")
    logger.error("Something failed")
    sentry_sdk.flush()

    assert [event.get("logentry", {}).get("message") for event in sentry] == ["Something failed"]
    assert "ann@example.com" not in repr(sentry)
