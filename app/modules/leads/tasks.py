import asyncio
import uuid

from app.modules.db import standalone_session
from app.modules.leads.delivery import deliver_lead
from app.modules.tasks.celery_app import celery_app

MAX_RETRIES = 5


async def _deliver(lead_id: str) -> bool:
    async with standalone_session() as session:
        return await deliver_lead(session, uuid.UUID(lead_id))


@celery_app.task(name="leads.deliver", bind=True, max_retries=MAX_RETRIES, ignore_result=True)
def deliver_lead_task(self, lead_id: str) -> None:
    """Deliver a lead; channels that failed for a transient reason are retried
    (1, 2, 4, 8, 16 minutes), channels that already got it are skipped."""
    if asyncio.run(_deliver(lead_id)):
        raise self.retry(countdown=60 * 2**self.request.retries)
