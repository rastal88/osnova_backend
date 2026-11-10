"""CSV files that open in a spreadsheet (standard library only).

``csv_response("users", header, rows)`` streams the file: UTF-8 with a BOM (Excel
needs it to read non-Latin text), dates as "2026-01-31 12:00:00" (UTC), values
that a spreadsheet would run as a formula made harmless. ``rows`` is an async
iterator, so a large table is never held in memory.
"""

import csv
import io
import re
from collections.abc import AsyncIterator, Iterable
from datetime import UTC, date, datetime
from typing import Any, Literal

from fastapi.responses import StreamingResponse

from app.core.i18n import get_language

Delimiter = Literal["comma", "semicolon"]
DELIMITERS: dict[str, str] = {"comma": ",", "semicolon": ";"}
# Where the comma is the decimal sign, spreadsheets expect ";" between columns
# and put a comma-separated file into one column
SEMICOLON_LANGUAGES = frozenset({"ru", "uk", "de", "fr", "es", "it", "pt", "pl", "nl", "tr"})
CHUNK = 64 * 1024

# "+7 (999) 123-45-67" and "-5" are not formulas
_NUMBER_LIKE = re.compile(r"[+-][\d\s().,-]*")


def default_delimiter() -> Delimiter:
    """By the request language."""
    return "semicolon" if get_language() in SEMICOLON_LANGUAGES else "comma"


def cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    text = str(value)
    # Spreadsheets run cells that start like this as formulas (CSV injection); the
    # values may come from anonymous visitors. An apostrophe makes them text.
    if text.startswith(("=", "@", "\t", "\r")) or (
        text.startswith(("+", "-")) and not _NUMBER_LIKE.fullmatch(text)
    ):
        return f"'{text}"
    return text


def csv_response(
    name: str,
    header: Iterable[str],
    rows: AsyncIterator[Iterable[Any]],
    delimiter: Delimiter | None = None,
) -> StreamingResponse:
    """A download named "<name>-<today>.csv"."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=DELIMITERS[delimiter or default_delimiter()])

    def take() -> str:
        text = buffer.getvalue()
        buffer.seek(0)
        buffer.truncate()
        return text

    async def body() -> AsyncIterator[str]:
        buffer.write("﻿")
        writer.writerow([cell(value) for value in header])
        async for row in rows:
            writer.writerow([cell(value) for value in row])
            if buffer.tell() >= CHUNK:
                yield take()
        yield take()

    filename = f"{name}-{datetime.now(UTC).date().isoformat()}.csv"
    return StreamingResponse(
        body(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            # Personal data: not for shared caches
            "Cache-Control": "no-store",
        },
    )
