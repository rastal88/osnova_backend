import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.modules.auth.dependencies import current_user
from app.modules.auth.models import User
from app.modules.db import get_async_session
from app.modules.notifications.models import Notification
from app.modules.notifications.texts import render

notifications_router = APIRouter(dependencies=[Depends(current_user)])


class NotificationRead(BaseModel):
    id: uuid.UUID
    kind: str
    title: str
    body: str
    link: str | None
    read: bool
    created_at: datetime


class NotificationPage(BaseModel):
    items: list[NotificationRead]
    total: int
    unread: int


class UnreadCount(BaseModel):
    unread: int


def read(notification: Notification) -> NotificationRead:
    title, body = render(notification.kind, notification.params)
    return NotificationRead(
        id=notification.id,
        kind=notification.kind,
        title=title,
        body=body,
        link=notification.link,
        read=notification.read_at is not None,
        created_at=notification.created_at,
    )


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def _unread(session: AsyncSession, user: User) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
    )
    return count or 0


@notifications_router.get("")
async def list_notifications(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    unread_only: bool = False,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
) -> NotificationPage:
    """The user's notifications, newest first, in the request language."""
    conditions = [Notification.user_id == user.id]
    if unread_only:
        conditions.append(Notification.read_at.is_(None))
    total = await session.scalar(select(func.count()).select_from(Notification).where(*conditions))
    rows = await session.scalars(
        select(Notification)
        .where(*conditions)
        .order_by(Notification.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    return NotificationPage(
        items=[read(item) for item in rows], total=total or 0, unread=await _unread(session, user)
    )


@notifications_router.get("/unread")
async def unread_count(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_async_session)
) -> UnreadCount:
    """Cheap enough to poll for the bell."""
    return UnreadCount(unread=await _unread(session, user))


@notifications_router.post("/read")
async def mark_all_read(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_async_session)
) -> UnreadCount:
    await session.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=_now())
    )
    await session.commit()
    return UnreadCount(unread=0)


@notifications_router.post("/{notification_id}/read")
async def mark_read(
    notification_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
) -> NotificationRead:
    notification = await session.get(Notification, notification_id)
    if notification is None or notification.user_id != user.id:
        raise AppError(404, "not_found")
    if notification.read_at is None:
        notification.read_at = _now()
        await session.commit()
    return read(notification)


@notifications_router.delete("/{notification_id}", status_code=204)
async def delete_notification(
    notification_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
) -> Response:
    notification = await session.get(Notification, notification_id)
    if notification is None or notification.user_id != user.id:
        raise AppError(404, "not_found")
    await session.delete(notification)
    await session.commit()
    return Response(status_code=204)
