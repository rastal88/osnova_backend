from fastapi import Request

from app.modules.db import app_session
from app.modules.leads.models import Lead


async def store_lead(record: dict, request: Request) -> None:
    """Form receiver (app.core.forms.delivery): keep the submission as a Lead."""
    async with app_session(request.app) as session:
        session.add(Lead(form=record["form"], data=record["data"], language=record["language"]))
        await session.commit()
