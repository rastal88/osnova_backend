import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.db import Base


class AuditRecord(Base):
    """One admin action: who, what, when (app/modules/admin/audit.py). Never changed."""

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None), index=True
    )
    # The account may be deleted later: its email stays in the record
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    actor_email: Mapped[str] = mapped_column(String(320))
    ip: Mapped[str | None] = mapped_column(String(45))
    # E.g. "users.block", "roles.update"
    action: Mapped[str] = mapped_column(String(64), index=True)
    # The id of what was changed and how people know it (an email, a name)
    target_id: Mapped[str | None] = mapped_column(String(64))
    target: Mapped[str | None] = mapped_column(String(320))
    # Field -> [before, after]; for an export, the filters it used
    changes: Mapped[dict[str, Any] | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
