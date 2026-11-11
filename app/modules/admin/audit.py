"""Admin → Audit log: who changed what in the admin and when.

A module declares its actions with ``audit_action("leads.delete")`` (their texts are
``audit.<action>`` in app/core/locales) and records them with the ``Audit``
dependency before the commit, so a change and its record are stored together:

    audit: Audit = Depends()
    ...
    audit(LEADS_DELETE, target_id=lead.id, target=lead.form)
    await session.commit()

``changes`` maps a field to ``[before, after]`` (see ``diff``); secret values are never
stored, only that they changed. An export records the filters it used. Records are
read with ``audit.read`` and never changed through the API; the nightly cleanup
removes those older than AUDIT_KEEP_DAYS (app/modules/admin/cleanup.py).
"""

import uuid
from collections.abc import Iterable
from datetime import date, datetime, time, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import has_translation, translate
from app.core.rate_limit import client_address
from app.modules.admin.models import AuditRecord
from app.modules.auth.dependencies import current_user, require
from app.modules.auth.models import User
from app.modules.auth.permissions import permission
from app.modules.db import get_async_session

AUDIT_READ = permission("audit.read")

# Shown instead of a secret value
SECRET = "********"

_actions: set[str] = set()


def audit_action(name: str) -> str:
    """Declare an action of the audit log, e.g. "users.block"; returns the name."""
    _actions.add(name)
    return name


def all_actions() -> set[str]:
    return set(_actions)


def diff(
    before: dict[str, Any], after: dict[str, Any], secret: Iterable[str] = ()
) -> dict[str, list[Any]]:
    """Fields that differ, as ``{field: [before, after]}``; secret ones are masked."""
    hidden = set(secret)
    return {
        key: [SECRET, SECRET] if key in hidden else [before.get(key), after.get(key)]
        for key in sorted(before.keys() | after.keys())
        if before.get(key) != after.get(key)
    }


class Audit:
    """Dependency that adds a record of the signed-in user's action to the request session."""

    def __init__(
        self,
        request: Request,
        actor: User = Depends(current_user),
        session: AsyncSession = Depends(get_async_session),
    ):
        self.actor = actor
        self.session = session
        address = client_address(request)
        self.ip = None if address == "unknown" else address

    def __call__(
        self,
        action: str,
        *,
        target_id: Any = None,
        target: str | None = None,
        changes: dict[str, Any] | None = None,
    ) -> None:
        self.session.add(
            AuditRecord(
                actor_id=self.actor.id,
                actor_email=self.actor.email,
                ip=self.ip,
                action=action,
                target_id=None if target_id is None else str(target_id),
                target=target,
                changes=changes or None,
            )
        )


class AuditRead(BaseModel):
    id: uuid.UUID
    created_at: datetime
    actor_id: uuid.UUID | None
    actor_email: str
    ip: str | None
    action: str
    # The action in the request language
    title: str
    target_id: str | None
    target: str | None
    changes: dict[str, Any] | None


class AuditPage(BaseModel):
    items: list[AuditRead]
    total: int


class AuditAction(BaseModel):
    name: str
    title: str


def _title(action: str) -> str:
    key = f"audit.{action}"
    return translate(key) if has_translation(key) else action


def _read(record: AuditRecord) -> AuditRead:
    fields = {name: getattr(record, name) for name in AuditRead.model_fields if name != "title"}
    return AuditRead(**fields, title=_title(record.action))


SORT_COLUMNS = {
    "created_at": AuditRecord.created_at,
    "action": AuditRecord.action,
    "actor_email": AuditRecord.actor_email,
}
AuditSort = Literal[tuple(f"{sign}{name}" for name in SORT_COLUMNS for sign in ("", "-"))]  # type: ignore[valid-type]

audit_router = APIRouter(prefix="/audit", dependencies=[Depends(require(AUDIT_READ))])


@audit_router.get("/actions")
async def list_actions() -> list[AuditAction]:
    """Actions of the enabled modules, with texts in the request language (for filters)."""
    return [AuditAction(name=name, title=_title(name)) for name in sorted(_actions)]


def _conditions(
    q: str,
    action: str | None,
    actor: uuid.UUID | None,
    since: date | None,
    until: date | None,
) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if search := q.strip():
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        conditions.append(
            or_(
                AuditRecord.actor_email.ilike(pattern, escape="\\"),
                AuditRecord.target.ilike(pattern, escape="\\"),
            )
        )
    if actions := [value for value in (action or "").split(",") if value]:
        conditions.append(AuditRecord.action.in_(actions))
    if actor is not None:
        conditions.append(AuditRecord.actor_id == actor)
    if since is not None:
        conditions.append(AuditRecord.created_at >= datetime.combine(since, time()))
    if until is not None:
        # The whole last day
        conditions.append(AuditRecord.created_at < datetime.combine(until + timedelta(1), time()))
    return conditions


@audit_router.get("")
async def list_audit(
    q: str = Query("", max_length=100, description="Part of the actor email or the target"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    sort: AuditSort = "-created_at",  # type: ignore[valid-type]
    action: str | None = Query(None, description="Comma-separated actions"),
    actor: uuid.UUID | None = Query(None, description="The id of who acted"),
    since: date | None = Query(None, description="From this day (UTC)"),
    until: date | None = Query(None, description="Up to and including this day (UTC)"),
    session: AsyncSession = Depends(get_async_session),
) -> AuditPage:
    """The newest records first; the query matches the frontend DataTable."""
    conditions = _conditions(q, action, actor, since, until)
    total = await session.scalar(select(func.count()).select_from(AuditRecord).where(*conditions))
    column = SORT_COLUMNS[sort.lstrip("-")]
    rows = await session.scalars(
        select(AuditRecord)
        .where(*conditions)
        .order_by(column.desc() if sort.startswith("-") else column.asc())
        .order_by(AuditRecord.created_at.desc(), AuditRecord.id)
        .offset((page - 1) * size)
        .limit(size)
    )
    return AuditPage(
        items=[_read(record) for record in rows],
        total=total or 0,
    )
