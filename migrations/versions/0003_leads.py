"""leads

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-09 23:20:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("form", sa.String(length=64), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_leads_created_at"), "leads", ["created_at"], unique=False)
    op.create_index(op.f("ix_leads_form"), "leads", ["form"], unique=False)
    op.create_index(op.f("ix_leads_status"), "leads", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_leads_status"), table_name="leads")
    op.drop_index(op.f("ix_leads_form"), table_name="leads")
    op.drop_index(op.f("ix_leads_created_at"), table_name="leads")
    op.drop_table("leads")
