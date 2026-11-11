from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.modules.admin.models import AuditRecord
from app.settings import RetentionSettings


async def cleanup(session: AsyncSession) -> int:
    """Remove audit records older than Admin → Settings → Retention says (0: keep them);
    see app/modules/db/cleanup.py."""
    days = settings.get(RetentionSettings).audit_days
    if days <= 0:
        return 0
    before = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)
    result = await session.execute(delete(AuditRecord).where(AuditRecord.created_at < before))
    return result.rowcount
