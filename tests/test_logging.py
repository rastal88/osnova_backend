"""Logs: text by default, one JSON object per line with LOG_FORMAT=json."""

import json
import logging
import sys
import uuid

import pytest

from app.config import config
from app.core import logging_config
from app.core.logging_config import JsonFormatter
from app.core.request_id import RequestIdFilter, current_request_id


def _record(message="Hello %s", args=("Ann",), **extra) -> logging.LogRecord:
    record = logging.getLogger("app.test").makeRecord(
        "app.test", logging.INFO, __file__, 1, message, args, None, extra=extra
    )
    RequestIdFilter().filter(record)
    return record


def test_json_lines_have_the_fields_and_the_request_id():
    token = current_request_id.set("abc123")
    try:
        line = JsonFormatter().format(_record())
    finally:
        current_request_id.reset(token)
    entry = json.loads(line)
    assert entry["message"] == "Hello Ann"
    assert (entry["level"], entry["logger"], entry["request_id"]) == ("INFO", "app.test", "abc123")
    assert entry["time"].endswith("+00:00")
    assert "\n" not in line


def test_extra_fields_become_keys_and_any_value_is_written():
    request = uuid.uuid4()
    entry = json.loads(JsonFormatter().format(_record(status=201, request=request)))
    assert entry["status"] == 201
    assert entry["request"] == str(request)
    # The standard attributes of a record are not repeated
    assert "args" not in entry and "levelno" not in entry


def test_an_exception_comes_with_its_traceback():
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.getLogger("app.test").makeRecord(
            "app.test", logging.ERROR, __file__, 1, "Failed", (), sys.exc_info()
        )
    entry = json.loads(JsonFormatter().format(record))
    assert entry["exception"].startswith("Traceback")
    assert entry["exception"].endswith("ValueError: boom")


@pytest.fixture
def restore_logging():
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    yield
    root.handlers[:] = handlers
    root.setLevel(level)


def test_setup_picks_the_format_and_takes_over_uvicorn(monkeypatch, restore_logging):
    monkeypatch.setattr(config, "LOG_FORMAT", "json")
    monkeypatch.setattr(config, "LOG_LEVEL", "WARNING")
    logging.getLogger("uvicorn.error").addHandler(logging.NullHandler())
    logging_config.setup_logging()

    (handler,) = logging.getLogger().handlers
    assert isinstance(handler.formatter, JsonFormatter)
    assert logging.getLogger().level == logging.WARNING
    uvicorn = logging.getLogger("uvicorn.error")
    assert uvicorn.handlers == [] and uvicorn.propagate is True

    monkeypatch.setattr(config, "LOG_FORMAT", "text")
    logging_config.setup_logging()
    (handler,) = logging.getLogger().handlers
    assert not isinstance(handler.formatter, JsonFormatter)


@pytest.mark.anyio
async def test_requests_are_logged_with_fields(client, caplog):
    with caplog.at_level(logging.INFO, logger="app.core.middlewares"):
        await client.get("/api/v1/health")
    (record,) = [r for r in caplog.records if r.name == "app.core.middlewares"]
    assert (record.method, record.path, record.status) == ("GET", "/api/v1/health", 200)
    assert isinstance(record.duration_ms, int)
