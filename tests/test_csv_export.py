import csv
import io
import logging
from datetime import date, datetime

import pytest
from sqlalchemy import update

from app.core.csv_export import cell, csv_response
from app.modules.leads.models import Lead
from tests.conftest import create_user, login

USERS = "/api/v1/admin/users/export"
LEADS = "/api/v1/admin/leads/export"
CONTACT = {
    "name": "Ann",
    "email": "ann@example.com",
    "topic": "order",
    "message": "Please call me back tomorrow",
    "consent": True,
}


def _table(response, delimiter=",") -> list[list[str]]:
    assert response.status_code == 200, response.text
    assert response.content.startswith(b"\xef\xbb\xbf")
    text = response.content.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(text), delimiter=delimiter))


async def _admin(auth_client, role="moderator"):
    client, session_factory = auth_client
    await create_user(session_factory, f"{role}@example.com", role)
    await login(client, f"{role}@example.com")
    return client, session_factory


def test_cell_formats_values_and_disarms_formulas():
    assert cell(None) == ""
    assert cell(datetime(2026, 1, 31, 12, 0, 5)) == "2026-01-31 12:00:05"
    assert cell(date(2026, 1, 31)) == "2026-01-31"
    assert cell(5) == "5"
    for formula in ("=1+1", "@SUM(A1)", "+cmd|' /C calc'!A0", "-2+3+cmd", "\t=1"):
        assert cell(formula) == f"'{formula}"
    # Phones and numbers stay as typed
    for plain in ("+7 (999) 123-45-67", "-5", "-1,5", "a=b", "ann@example.com"):
        assert cell(plain) == plain


@pytest.mark.anyio
async def test_response_streams_in_chunks_with_a_bom():
    async def rows():
        for number in range(3000):
            yield [number, "x" * 100]

    response = csv_response("things", ["N", "Text"], rows(), "semicolon")
    chunks = [chunk async for chunk in response.body_iterator]

    assert len(chunks) > 1
    text = "".join(chunks)
    assert text.startswith("﻿N;Text\r\n0;")
    assert text.count("\r\n") == 3001
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert response.headers["content-disposition"].startswith('attachment; filename="things-20')
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.anyio
async def test_users_export_follows_the_list_query(auth_client, caplog):
    client, session_factory = await _admin(auth_client)
    for name in ("alice", "bob", "carol"):
        await create_user(session_factory, f"{name}@example.com", "user")

    with caplog.at_level(logging.INFO, logger="app.modules.admin.users"):
        table = _table(await client.get(USERS, params={"sort": "email"}))
    assert table[0] == [
        "Email",
        "Name",
        "Role",
        "Active",
        "Email confirmed",
        "Signed up",
        "Last sign-in",
    ]
    assert [row[0] for row in table[1:]] == [
        "alice@example.com",
        "bob@example.com",
        "carol@example.com",
        "moderator@example.com",
    ]
    assert table[1][2:5] == ["user", "Yes", "No"]
    assert len(table[1][5]) == len("2026-01-31 12:00:00")
    assert "exported 4 users" in caplog.text

    # No pages: everything that matches, with the same search and filters
    table = _table(await client.get(USERS, params={"role": "user", "sort": "-email"}))
    assert [row[0] for row in table[1:]] == [
        "carol@example.com",
        "bob@example.com",
        "alice@example.com",
    ]
    table = _table(await client.get(USERS, params={"q": "BOB"}))
    assert [row[0] for row in table[1:]] == ["bob@example.com"]

    # Russian: translated header, ";" between columns (the Excel default there)
    response = await client.get(USERS, headers={"Accept-Language": "ru"})
    assert _table(response, ";")[0][:3] == ["Email", "Имя", "Роль"]
    response = await client.get(
        USERS, params={"delimiter": "comma"}, headers={"Accept-Language": "ru"}
    )
    assert _table(response)[0][1] == "Имя"
    assert (await client.get(USERS, params={"delimiter": "tab"})).status_code == 422


@pytest.mark.anyio
async def test_leads_export_has_a_column_per_field(auth_client):
    client, session_factory = await _admin(auth_client)
    for changes in ({}, {"name": "=HYPERLINK(1)", "email": "bob@example.com", "topic": None}):
        response = await client.post("/api/v1/forms/contact", json={**CONTACT, **changes})
        assert response.status_code == 200, response.text
    async with session_factory() as session:
        # An answer to a field the form no longer has
        await session.execute(
            update(Lead)
            .where(Lead.data["name"].as_string() == "Ann")
            .values(data={**CONTACT, "budget": "1000"}, status="done")
        )
        await session.commit()

    table = _table(await client.get(LEADS, params={"sort": "created_at"}))
    header = table[0]
    assert header[:4] == ["Date", "Form", "Status", "Language"]
    assert header[-1] == "Other"
    ann = dict(zip(header, table[1], strict=True))
    bob = dict(zip(header, table[2], strict=True))
    assert ann["Form"] == "Contact us"
    assert ann["Status"] == "done"
    assert ann["Language"] == "en"
    # Answers as the visitor saw them: option labels, yes / no
    assert "Order" in ann.values()
    assert "Yes" in ann.values()
    assert ann["Other"] == '{"budget": "1000"}'
    assert bob["Other"] == ""
    # A formula typed into a public form stays text
    assert "'=HYPERLINK(1)" in bob.values()

    table = _table(await client.get(LEADS, params={"status": "done"}))
    assert len(table) == 2
    table = _table(await client.get(LEADS, params={"q": "bob@"}))
    assert len(table) == 2


@pytest.mark.anyio
async def test_export_is_for_admins(auth_client):
    client, session_factory = auth_client
    for url in (USERS, LEADS):
        assert (await client.get(url)).status_code == 401
    await create_user(session_factory, "user@example.com", "user")
    await login(client, "user@example.com")
    for url in (USERS, LEADS):
        assert (await client.get(url)).status_code == 403
