import smtplib
from typing import Any

from fastapi import APIRouter, Body, Depends
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.i18n import user_language
from app.core.mail import deliver, render_mail
from app.core.mail.settings import MailSettings
from app.core.settings import SettingsGroup, secret_fields, settings
from app.core.settings.schema import SettingsGroupDescription, describe_group
from app.modules.admin.audit import Audit, audit_action, diff
from app.modules.auth.dependencies import require_admin
from app.modules.auth.models import User
from app.modules.db import get_async_session
from app.modules.settings.service import group_permission, groups_by_name, save_settings
from app.settings import SiteSettings

SETTINGS_UPDATE = audit_action("settings.update")

# Groups without secrets are seen by everyone in the admin area; changing a group, and
# seeing one with secrets (mail, protection), needs settings.<group>.
settings_router = APIRouter(dependencies=[Depends(require_admin)])


class MailTestResult(BaseModel):
    ok: bool
    # What the mail server answered
    error: str | None


def _get_group(name: str) -> type[SettingsGroup]:
    group = groups_by_name.get(name)
    if group is None:
        raise AppError(404, "settings_group_not_found")
    return group


def _may_change(user: User, group: type[SettingsGroup]) -> bool:
    return group_permission(group.group) in user.permissions


def _describe(user: User, group: type[SettingsGroup], value: SettingsGroup):
    description = describe_group(group, value)
    description.editable = _may_change(user, group)
    return description


@settings_router.get("")
async def list_settings(user: User = Depends(require_admin)) -> list[SettingsGroupDescription]:
    """The groups the user may see, with their form description and current values."""
    return [
        _describe(user, group, settings.get(group))
        for group in groups_by_name.values()
        if not secret_fields(group) or _may_change(user, group)
    ]


@settings_router.post("/mail/test")
async def test_mail(user: User = Depends(require_admin)) -> MailTestResult:
    """Send a test email to the signed-in user now, with the saved mail settings; the
    answer carries the error of the mail server."""
    if not _may_change(user, MailSettings):
        raise AppError(403, "forbidden")
    site = settings.get(SiteSettings).name
    message = render_mail("mail_test", user.email, user_language(user.language), site=site)
    try:
        await run_in_threadpool(deliver, message)
    except (OSError, smtplib.SMTPException) as exc:
        return MailTestResult(ok=False, error=str(exc) or exc.__class__.__name__)
    return MailTestResult(ok=True, error=None)


@settings_router.put("/{name}")
async def update_settings(
    name: str,
    payload: dict[str, Any] = Body(...),
    user: User = Depends(require_admin),
    audit: Audit = Depends(),
    session: AsyncSession = Depends(get_async_session),
) -> SettingsGroupDescription:
    group = _get_group(name)
    if not _may_change(user, group):
        raise AppError(403, "forbidden")

    def record(old: SettingsGroup, new: SettingsGroup) -> None:
        before, after = old.model_dump(mode="json"), new.model_dump(mode="json")
        if changes := diff(before, after, secret_fields(group)):
            audit(SETTINGS_UPDATE, target_id=group.group, target=group.group, changes=changes)

    try:
        value = await save_settings(session, group, payload, before_commit=record)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc
    return _describe(user, group, value)
