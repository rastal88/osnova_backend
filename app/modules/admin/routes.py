from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.core.mail.settings import MailSettings
from app.core.settings import settings
from app.modules.admin.access import access_router
from app.modules.admin.audit import audit_router
from app.modules.admin.users import users_router
from app.modules.auth.dependencies import require_admin
from app.modules.auth.models import RoleRecord, User
from app.modules.db import get_async_session

# Every endpoint of the admin area requires the admin.access permission.
admin_router = APIRouter(dependencies=[Depends(require_admin)])


class AdminSystem(BaseModel):
    """How this installation is set up, for the dashboard; no secrets."""

    # Where the form and sign-in rate limits count: in each process, or shared in Redis
    rate_limit_storage: Literal["memory", "redis"]
    # Where uploaded files are kept; none without the files module
    files_storage: Literal["local", "s3"] | None
    # How emails go out (Admin → Settings → Mail): "console" only writes them to the log
    mail_backend: Literal["console", "smtp"]
    # Sessions: stateless JWT cookies, or kept in Redis
    auth_strategy: Literal["jwt", "redis"]
    # Errors are sent to Sentry (SENTRY_DSN)
    error_tracking: bool
    log_format: Literal["text", "json"]


class AdminOverview(BaseModel):
    users: int
    active_users: int
    # By the slug of a role, every role of the project
    users_by_role: dict[str, int]
    system: AdminSystem


def system_info(modules: list[str]) -> AdminSystem:
    return AdminSystem(
        rate_limit_storage=config.RATE_LIMIT_STORAGE,
        files_storage=config.FILES_STORAGE if "files" in modules else None,
        mail_backend=settings.get(MailSettings).backend,
        auth_strategy=config.AUTH_STRATEGY,
        error_tracking=bool(config.SENTRY_DSN),
        log_format=config.LOG_FORMAT,
    )


@admin_router.get("/overview")
async def admin_overview(
    request: Request, session: AsyncSession = Depends(get_async_session)
) -> AdminOverview:
    """Counters and the setup of the installation for the admin dashboard."""
    rows = await session.execute(select(User.role, func.count()).group_by(User.role))
    by_role = dict(rows.all())
    roles = await session.scalars(
        select(RoleRecord.slug).order_by(RoleRecord.system.desc(), RoleRecord.name)
    )
    active = await session.scalar(select(func.count()).where(User.is_active.is_(True)))
    return AdminOverview(
        users=sum(by_role.values()),
        active_users=active or 0,
        users_by_role={slug: by_role.get(slug, 0) for slug in roles},
        system=system_info(request.app.state.modules),
    )


admin_router.include_router(users_router)
admin_router.include_router(access_router)
admin_router.include_router(audit_router)
