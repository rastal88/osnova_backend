import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.db import Base

# A plain string column: a new status needs no migration
LeadStatus = Literal["new", "done"]


class Lead(Base):
    """One submission of a form (app/forms.py)."""

    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    form: Mapped[str] = mapped_column(String(64), index=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    language: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(16), default="new", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None), index=True
    )
    # Delivery to each channel: {entity id: {channel, type, status, error, at}}
    deliveries: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict
    )
