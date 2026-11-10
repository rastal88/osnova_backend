"""Admin → Leads. The list query matches the frontend DataTable: `q`, `page`,
`size`, `sort` (`-` for descending) and filters `form`, `status`.
`GET /admin/leads/export` takes the same query without pages and answers with a
CSV file of everything that matches."""

import json
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import ColumnElement, String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.csv_export import Delimiter, csv_response
from app.core.errors import AppError
from app.core.forms.schema import FormDescription, describe
from app.core.i18n import get_language, translate
from app.forms import FORMS
from app.modules.auth.dependencies import require_admin, require_any_role
from app.modules.auth.models import User
from app.modules.auth.roles import Role
from app.modules.db import app_session, get_async_session
from app.modules.entities.models import Entity
from app.modules.entities.service import parse_params
from app.modules.leads.channels import GROUP, LeadMessage
from app.modules.leads.models import Lead, LeadStatus

logger = logging.getLogger(__name__)

leads_router = APIRouter(dependencies=[Depends(require_admin)])

SORT_COLUMNS = {"created_at": Lead.created_at, "form": Lead.form, "status": Lead.status}
LeadSort = Literal[tuple(f"{sign}{name}" for name in SORT_COLUMNS for sign in ("", "-"))]  # type: ignore[valid-type]
STATUSES: tuple[str, ...] = ("new", "done")


class LeadDelivery(BaseModel):
    channel: str
    type: str
    status: Literal["sent", "failed"]
    error: str | None
    # The receiver refused it: not retried
    final: bool = False
    at: datetime


class LeadRead(BaseModel):
    id: uuid.UUID
    form: str
    data: dict[str, Any]
    language: str
    status: LeadStatus
    created_at: datetime
    # By channel (entity) id
    deliveries: dict[str, LeadDelivery]


class ChannelTestResult(BaseModel):
    ok: bool
    error: str | None


class LeadPage(BaseModel):
    items: list[LeadRead]
    total: int


class LeadUpdate(BaseModel):
    status: LeadStatus


class LeadDay(BaseModel):
    date: date
    count: int


class LeadStats(BaseModel):
    total: int
    by_status: dict[str, int]
    # Every day of the period, oldest first, days without leads included (UTC)
    by_day: list[LeadDay]


def _values(raw: str | None, allowed: tuple[str, ...]) -> list[str]:
    return [value for value in (raw or "").split(",") if value in allowed]


@leads_router.get("/forms")
async def lead_forms() -> list[FormDescription]:
    """The project's forms with translated field labels, to show and filter leads."""
    return [describe(form) for form in FORMS]


@leads_router.get("/stats")
async def lead_stats(
    days: int = Query(14, ge=1, le=90, description="Length of the by_day period"),
    session: AsyncSession = Depends(get_async_session),
) -> LeadStats:
    """Counters and leads per day, for the admin overview."""
    by_status = dict(
        (await session.execute(select(Lead.status, func.count()).group_by(Lead.status))).all()
    )
    today = datetime.now(UTC).date()
    first = today - timedelta(days=days - 1)
    day = func.date(Lead.created_at)
    rows = await session.execute(
        select(day, func.count())
        .where(Lead.created_at >= datetime.combine(first, datetime.min.time()))
        .group_by(day)
    )
    # PostgreSQL returns a date, SQLite a "YYYY-MM-DD" string
    counts = {str(value)[:10]: count for value, count in rows.all()}
    period = [first + timedelta(days=offset) for offset in range(days)]
    return LeadStats(
        total=sum(by_status.values()),
        by_status={status: by_status.get(status, 0) for status in STATUSES},
        by_day=[LeadDay(date=item, count=counts.get(str(item), 0)) for item in period],
    )


@leads_router.post(
    "/channels/{channel_id}/test", dependencies=[Depends(require_any_role(Role.ROOT))]
)
async def test_channel(
    channel_id: uuid.UUID, session: AsyncSession = Depends(get_async_session)
) -> ChannelTestResult:
    """Send a test message through one channel now and report the result."""
    entity = await session.get(Entity, channel_id)
    channel = parse_params(entity) if entity else None
    if entity is None or channel is None or channel.group != GROUP:
        raise AppError(404, "not_found")
    message = LeadMessage(
        id=str(uuid.uuid4()),
        form="test",
        title=translate("leads.test_title"),
        language=get_language(),
        created_at=datetime.now(UTC).isoformat(),
        fields=[(translate("leads.test_field"), translate("leads.test_text"))],
        data={"test": True},
    )
    try:
        await run_in_threadpool(channel.send, message)  # type: ignore[attr-defined]
    except Exception as exc:
        return ChannelTestResult(ok=False, error=f"{type(exc).__name__}: {exc}"[:500])
    return ChannelTestResult(ok=True, error=None)


def _conditions(q: str, form: str | None, status: str | None) -> list[ColumnElement[bool]]:
    """What the list and the export show."""
    conditions: list[ColumnElement[bool]] = []
    if search := q.strip():
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        conditions.append(cast(Lead.data, String).ilike(f"%{escaped}%", escape="\\"))
    if forms := _values(form, tuple(item.name for item in FORMS)):
        conditions.append(Lead.form.in_(forms))
    if statuses := _values(status, STATUSES):
        conditions.append(Lead.status.in_(statuses))
    return conditions


def _order(sort: str) -> ColumnElement[Any]:
    column = SORT_COLUMNS[sort.lstrip("-")]
    return column.desc() if sort.startswith("-") else column.asc()


@leads_router.get("")
async def list_leads(
    q: str = Query("", max_length=100, description="Text anywhere in the submitted data"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    sort: LeadSort = "-created_at",  # type: ignore[valid-type]
    form: str | None = Query(None, description="Comma-separated form names"),
    status: str | None = Query(None, description="Comma-separated: new, done"),
    session: AsyncSession = Depends(get_async_session),
) -> LeadPage:
    conditions = _conditions(q, form, status)
    total = await session.scalar(select(func.count()).select_from(Lead).where(*conditions))
    result = await session.scalars(
        select(Lead)
        .where(*conditions)
        .order_by(_order(sort), Lead.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    return LeadPage(
        items=[LeadRead.model_validate(lead, from_attributes=True) for lead in result],
        total=total or 0,
    )


@leads_router.get("/export", response_class=StreamingResponse)
async def export_leads(
    request: Request,
    q: str = Query("", max_length=100, description="Text anywhere in the submitted data"),
    sort: LeadSort = "-created_at",  # type: ignore[valid-type]
    form: str | None = Query(None, description="Comma-separated form names"),
    status: str | None = Query(None, description="Comma-separated: new, done"),
    delimiter: Delimiter | None = Query(None, description="Default: by the request language"),
    admin: User = Depends(require_admin),
) -> StreamingResponse:
    """Every lead the list shows with this query, as a CSV file: a column per field of
    the chosen forms (all forms without the filter), answers as the visitor saw them."""
    names = _values(form, tuple(item.name for item in FORMS))
    forms = {item.name: describe(item) for item in FORMS if not names or item.name in names}
    # Field name -> label; forms that share a field name share the column
    columns: dict[str, str] = {}
    options: dict[tuple[str, str], dict[str, str]] = {}
    for description in forms.values():
        for field in description.fields:
            columns.setdefault(field.name, field.label)
            options[description.name, field.name] = {o.value: o.label for o in field.options}
    yes_no = {True: translate("export.yes"), False: translate("export.no")}

    def text(value: Any, labels: dict[str, str]) -> Any:
        if isinstance(value, bool):
            return yes_no[value]
        if isinstance(value, list):
            return ", ".join(labels.get(str(item), str(item)) for item in value)
        return labels.get(value, value) if isinstance(value, str) else value

    statement = (
        select(Lead)
        .where(*_conditions(q, form, status))
        .order_by(_order(sort), Lead.created_at.desc())
    )

    async def rows() -> AsyncIterator[list[Any]]:
        count = 0
        # Its own session: the request's one may be closed before the file is sent
        async with app_session(request.app) as session:
            result = await session.stream_scalars(statement.execution_options(yield_per=500))
            async for lead in result:
                count += 1
                # Answers to fields the form no longer has
                other = {key: value for key, value in lead.data.items() if key not in columns}
                yield [
                    lead.created_at,
                    forms[lead.form].title if lead.form in forms else lead.form,
                    lead.status,
                    lead.language,
                    *(
                        text(lead.data.get(name), options.get((lead.form, name), {}))
                        for name in columns
                    ),
                    json.dumps(other, ensure_ascii=False) if other else None,
                ]
        logger.info("User %s exported %d leads.", admin.id, count)

    header = [
        *(translate(f"export.{name}") for name in ("created_at", "form", "status", "language")),
        *columns.values(),
        translate("export.other"),
    ]
    return csv_response("leads", header, rows(), delimiter)


async def _get_lead(session: AsyncSession, lead_id: uuid.UUID) -> Lead:
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise AppError(404, "not_found")
    return lead


@leads_router.patch("/{lead_id}")
async def update_lead(
    lead_id: uuid.UUID, changes: LeadUpdate, session: AsyncSession = Depends(get_async_session)
) -> LeadRead:
    lead = await _get_lead(session, lead_id)
    lead.status = changes.status
    await session.commit()
    return LeadRead.model_validate(lead, from_attributes=True)


@leads_router.delete("/{lead_id}", status_code=204)
async def delete_lead(
    lead_id: uuid.UUID, session: AsyncSession = Depends(get_async_session)
) -> Response:
    """Removes the submission and its personal data for good."""
    await session.delete(await _get_lead(session, lead_id))
    await session.commit()
    return Response(status_code=204)
