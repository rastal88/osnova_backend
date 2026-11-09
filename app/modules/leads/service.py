from fastapi import Request

from app.modules.db import app_session
from app.modules.entities.service import enabled_entities
from app.modules.leads.channels import GROUP
from app.modules.leads.delivery import dispatch
from app.modules.leads.models import Lead


async def store_lead(record: dict, request: Request) -> None:
    """Form receiver (app.core.forms.delivery): keep the submission as a Lead,
    then deliver it to the enabled channels in the background."""
    async with app_session(request.app) as session:
        lead = Lead(form=record["form"], data=record["data"], language=record["language"])
        session.add(lead)
        await session.commit()
        has_channels = bool(await enabled_entities(session, GROUP))
    if has_channels:
        await dispatch(request.app, lead.id)
