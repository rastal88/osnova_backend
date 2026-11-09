import logging

from fastapi import Request

from app.config import config
from app.modules.db import app_session
from app.modules.entities.service import enabled_entities
from app.modules.leads.channels import GROUP
from app.modules.leads.delivery import dispatch
from app.modules.leads.models import Lead

logger = logging.getLogger(__name__)


async def store_lead(record: dict, request: Request) -> None:
    """Form receiver (app.core.forms.delivery): keep the submission as a Lead,
    then deliver it to the enabled channels in the background."""
    async with app_session(request.app) as session:
        lead = Lead(form=record["form"], data=record["data"], language=record["language"])
        session.add(lead)
        await session.commit()
        has_channels = bool(await enabled_entities(session, GROUP))
        if config.NOTIFICATIONS_ENABLED:
            try:
                await _notify_admins(session, lead)
            except Exception:
                # The lead is stored: an error here must not make the visitor send it again
                logger.exception("Lead %s: admin notification failed", lead.id)
    if has_channels:
        await dispatch(request.app, lead.id)


async def _notify_admins(session, lead: Lead) -> None:
    """Example of a notification: admins get a bell item that opens Admin → Leads."""
    from app.modules.auth.roles import ADMIN_ROLES
    from app.modules.notifications.service import notify, users_with_roles

    params = {"summary": _summary(lead.data)}
    admins = await users_with_roles(session, *ADMIN_ROLES)
    await notify(session, admins, "lead_new", params, link="/admin/leads")


def _summary(data: dict) -> str:
    """The first two short text answers, e.g. "Ann · ann@example.com"."""
    values = [v for v in data.values() if isinstance(v, str) and v.strip() and len(v) <= 100]
    return " · ".join(values[:2])
