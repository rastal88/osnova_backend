from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.modules.admin.models import AuditRecord


async def cleanup(session: AsyncSession) -> int:
    """Remove audit records older than AUDIT_KEEP_DAYS (0: keep them); see
    app/modules/db/cleanup.py."""
    if config.AUDIT_KEEP_DAYS <= 0:
        return 0
    before = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=config.AUDIT_KEEP_DAYS)
    result = await session.execute(delete(AuditRecord).where(AuditRecord.created_at < before))
    return result.rowcount
