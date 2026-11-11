from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest
from celery.schedules import crontab
from sqlalchemy import select, update
from typer.testing import CliRunner

from app.config import config
from app.modules.admin.models import AuditRecord
from app.modules.auth.models import User
from app.modules.db import cleanup
from app.modules.notifications.models import Notification
from app.modules.tasks.celery_app import celery_app
from app.modules.tasks.tasks import cleanup_task
from tests.conftest import create_user


def _ago(days: int) -> datetime:
    return datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)


@pytest.fixture
def cleanup_session(database, monkeypatch):
    """run_cleanup works on the test database."""

    @asynccontextmanager
    async def test_session():
        async with database() as session:
            yield session

    monkeypatch.setattr(cleanup, "standalone_session", test_session)
    return database


async def _user(session_factory, email: str, **values) -> User:
    await create_user(session_factory, email, values.pop("role", "user"))
    async with session_factory() as session:
        if values:
            await session.execute(update(User).where(User.email == email).values(**values))
            await session.commit()
        return await session.scalar(select(User).where(User.email == email))


@pytest.mark.anyio
async def test_old_read_notifications_are_removed(cleanup_session, monkeypatch):
    user = await _user(cleanup_session, "ann@example.com")
    async with cleanup_session() as session:
        session.add_all(
            [
                Notification(
                    user_id=user.id, kind=kind, params={}, created_at=_ago(age), read_at=read_at
                )
                for kind, age, read_at in (
                    ("old_read", 100, _ago(99)),
                    ("old_unread", 100, None),
                    ("new_read", 10, _ago(1)),
                )
            ]
        )
        await session.commit()

    assert await cleanup.run_cleanup() == {"notifications": 1, "auth": 0, "admin": 0}

    async with cleanup_session() as session:
        kinds = set(await session.scalars(select(Notification.kind)))
    assert kinds == {"old_unread", "new_read"}

    # 0 keeps everything
    monkeypatch.setattr(config, "NOTIFICATIONS_KEEP_DAYS", 0)
    async with cleanup_session() as session:
        await session.execute(update(Notification).values(read_at=_ago(99), created_at=_ago(99)))
        await session.commit()
    assert (await cleanup.run_cleanup())["notifications"] == 0


@pytest.mark.anyio
async def test_never_confirmed_accounts_are_removed_when_asked(cleanup_session, monkeypatch):
    old = {"is_verified": False, "date_created": _ago(30)}
    await _user(cleanup_session, "gone@example.com", **old)
    await _user(cleanup_session, "fresh@example.com", is_verified=False, date_created=_ago(1))
    await _user(cleanup_session, "confirmed@example.com", is_verified=True, date_created=_ago(30))
    await _user(cleanup_session, "signed-in@example.com", last_login=_ago(20), **old)
    await _user(cleanup_session, "staff@example.com", role="moderator", **old)

    # Off by default
    assert (await cleanup.run_cleanup())["auth"] == 0

    monkeypatch.setattr(config, "UNVERIFIED_ACCOUNT_DAYS", 7)
    assert (await cleanup.run_cleanup())["auth"] == 1
    async with cleanup_session() as session:
        emails = set(await session.scalars(select(User.email)))
    assert emails == {
        "fresh@example.com",
        "confirmed@example.com",
        "signed-in@example.com",
        "staff@example.com",
    }


@pytest.mark.anyio
async def test_old_audit_records_are_removed(cleanup_session, monkeypatch):
    async with cleanup_session() as session:
        session.add_all(
            [
                AuditRecord(actor_email="root@example.com", action=action, created_at=_ago(age))
                for action, age in (("roles.create", 400), ("roles.update", 300))
            ]
        )
        await session.commit()

    assert (await cleanup.run_cleanup())["admin"] == 1
    async with cleanup_session() as session:
        assert list(await session.scalars(select(AuditRecord.action))) == ["roles.update"]

    # 0 keeps everything
    monkeypatch.setattr(config, "AUDIT_KEEP_DAYS", 0)
    async with cleanup_session() as session:
        await session.execute(update(AuditRecord).values(created_at=_ago(1000)))
        await session.commit()
    assert (await cleanup.run_cleanup())["admin"] == 0


@pytest.mark.anyio
async def test_failed_job_does_not_stop_the_others(cleanup_session, monkeypatch, caplog):
    from app.modules.notifications import cleanup as notifications_cleanup

    async def broken(session):
        raise RuntimeError("boom")

    monkeypatch.setattr(notifications_cleanup, "cleanup", broken)
    assert await cleanup.run_cleanup() == {"auth": 0, "admin": 0}
    assert "Cleanup of notifications failed" in caplog.text


def test_cleanup_is_scheduled_every_night():
    entry = celery_app.conf.beat_schedule["cleanup"]
    assert entry["task"] == cleanup_task.name == "maintenance.cleanup"
    assert entry["schedule"] == crontab(hour=3, minute=30)
    assert entry["task"] in celery_app.tasks


def test_task_and_command_run_the_cleanup(monkeypatch):
    import manage

    calls = []

    async def fake_cleanup():
        calls.append(1)
        return {"notifications": 3}

    monkeypatch.setattr(cleanup, "run_cleanup", fake_cleanup)
    cleanup_task()
    result = CliRunner().invoke(manage.app, ["cleanup"])
    assert result.exit_code == 0, result.output
    assert "notifications: 3" in result.output
    assert len(calls) == 2
