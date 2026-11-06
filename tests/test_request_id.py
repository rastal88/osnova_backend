import logging

import pytest

from app.core.request_id import RequestIdFilter, current_request_id


@pytest.mark.anyio
async def test_request_id_is_generated(client):
    first = await client.get("/api/v1/health")
    second = await client.get("/api/v1/health")

    assert len(first.headers["X-Request-ID"]) == 32
    assert first.headers["X-Request-ID"] != second.headers["X-Request-ID"]


@pytest.mark.anyio
async def test_incoming_request_id_is_kept(client):
    response = await client.get("/api/v1/health", headers={"X-Request-ID": "abc-123"})
    assert response.headers["X-Request-ID"] == "abc-123"


@pytest.mark.anyio
async def test_unsafe_request_id_is_replaced(client):
    response = await client.get("/api/v1/health", headers={"X-Request-ID": "bad id\tvalue"})
    assert response.headers["X-Request-ID"] != "bad id\tvalue"
    assert len(response.headers["X-Request-ID"]) == 32


@pytest.mark.anyio
async def test_request_is_logged_with_id(client, caplog):
    caplog.set_level("INFO", logger="app.core.middlewares")
    caplog.handler.addFilter(RequestIdFilter())
    response = await client.get("/api/v1/health?token=secret")

    [record] = [r for r in caplog.records if r.name == "app.core.middlewares"]
    assert record.request_id == response.headers["X-Request-ID"]
    message = record.getMessage()
    assert message.startswith("GET /api/v1/health 200 ")
    assert "secret" not in message


def test_filter_outside_request():
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "message", None, None)
    RequestIdFilter().filter(record)
    assert record.request_id == "-" == current_request_id.get()
