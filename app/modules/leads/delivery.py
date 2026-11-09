"""Delivering a stored lead to the enabled channels (app/modules/leads/channels.py).

With background tasks on, the Celery task `leads.deliver` does it and retries
failed channels with backoff; otherwise it runs in the web process right after
the response, once. The result per channel is kept in Lead.deliveries.
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.core.forms.schema import describe
from app.core.i18n import current_language, translate
from app.forms import FORMS
from app.modules.db import app_session
from app.modules.entities.service import enabled_entities
from app.modules.leads.channels import GROUP, DeliveryRejected, LeadMessage
from app.modules.leads.models import Lead

logger = logging.getLogger(__name__)
forms_by_name = {form.name: form for form in FORMS}


def _text(value: object, options: dict[str, str]) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        return translate("leads.yes" if value else "leads.no")
    if isinstance(value, list):
        return ", ".join(options.get(str(item), str(item)) for item in value)
    return options.get(str(value), str(value))


def lead_message(lead: Lead) -> LeadMessage:
    """The lead as text in its own language, with the form's labels."""
    token = current_language.set(lead.language)
    try:
        form = forms_by_name.get(lead.form)
        description = describe(form) if form else None
        fields: list[tuple[str, str]] = []
        for field in description.fields if description else []:
            options = {option.value: option.label for option in field.options}
            fields.append((field.label, _text(lead.data.get(field.name), options)))
        # Answers to fields the form no longer has are kept under their names
        names = {field.name for field in form.fields} if form else set()
        fields += [(key, _text(value, {})) for key, value in lead.data.items() if key not in names]
        title = translate("leads.new", form=description.title if description else lead.form)
    finally:
        current_language.reset(token)
    return LeadMessage(
        id=str(lead.id),
        form=lead.form,
        title=title,
        language=lead.language,
        created_at=lead.created_at.isoformat() + "Z",
        fields=fields,
        data=lead.data,
    )


async def deliver_lead(session: AsyncSession, lead_id: uuid.UUID) -> bool:
    """Send the lead to every enabled channel it has not reached yet (a channel that
    refused it is not tried again). Returns True when a failure is worth a retry."""
    lead = await session.get(Lead, lead_id)
    if lead is None:
        return False
    message = lead_message(lead)
    results = dict(lead.deliveries or {})
    retry = False
    for entity, channel in await enabled_entities(session, GROUP):
        key = str(entity.id)
        previous = results.get(key, {})
        if previous.get("status") == "sent" or previous.get("final"):
            continue
        result = {
            "channel": entity.name,
            "type": entity.type,
            "status": "sent",
            "error": None,
            "final": False,
        }
        try:
            await run_in_threadpool(channel.send, message)  # type: ignore[attr-defined]
        except DeliveryRejected as exc:
            result |= {"status": "failed", "error": str(exc)[:500], "final": True}
        except Exception as exc:
            result |= {"status": "failed", "error": f"{type(exc).__name__}: {exc}"[:500]}
            retry = True
        if result["status"] == "failed":
            logger.warning("Lead %s: %s failed: %s", lead.id, entity.name, result["error"])
        results[key] = result | {"at": datetime.now(UTC).isoformat()}
    lead.deliveries = results
    await session.commit()
    return retry


# Keeps in-process deliveries alive until they finish
_running: set[asyncio.Task] = set()


async def _in_process(app: FastAPI, lead_id: uuid.UUID) -> None:
    try:
        async with app_session(app) as session:
            await deliver_lead(session, lead_id)
    except Exception:
        logger.exception("Lead %s: delivery failed", lead_id)


async def dispatch(app: FastAPI, lead_id: uuid.UUID) -> None:
    """Start delivering a stored lead without delaying the response."""
    if config.BACKGROUND_TASKS_ENABLED:
        from app.modules.leads.tasks import deliver_lead_task

        try:
            await run_in_threadpool(deliver_lead_task.delay, str(lead_id))
            return
        except Exception:
            logger.exception("Lead %s: queue unavailable, delivering in process", lead_id)
    task = asyncio.create_task(_in_process(app, lead_id))
    _running.add(task)
    task.add_done_callback(_running.discard)
