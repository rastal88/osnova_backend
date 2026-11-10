"""Admin → Leads. The list query matches the frontend DataTable: `q`, `page`,
`size`, `sort` (`-` for descending) and filters `form`, `status`."""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.forms.schema import FormDescription, describe
from app.core.i18n import get_language, translate
from app.forms import FORMS
from app.modules.auth.dependencies import require_admin, require_any_role
from app.modules.auth.roles import Role
from app.modules.db import get_async_session
from app.modules.entities.models import Entity
from app.modules.entities.service import parse_params
from app.modules.leads.channels import GROUP, LeadMessage
from app.modules.leads.models import Lead, LeadStatus

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
    conditions = []
    if search := q.strip():
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        conditions.append(cast(Lead.data, String).ilike(f"%{escaped}%", escape="\\"))
    if forms := _values(form, tuple(item.name for item in FORMS)):
        conditions.append(Lead.form.in_(forms))
    if statuses := _values(status, STATUSES):
        conditions.append(Lead.status.in_(statuses))

    column = SORT_COLUMNS[sort.lstrip("-")]
    order = column.desc() if sort.startswith("-") else column.asc()
    total = await session.scalar(select(func.count()).select_from(Lead).where(*conditions))
    result = await session.scalars(
        select(Lead)
        .where(*conditions)
        .order_by(order, Lead.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    return LeadPage(
        items=[LeadRead.model_validate(lead, from_attributes=True) for lead in result],
        total=total or 0,
    )


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
