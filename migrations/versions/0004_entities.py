"""entities

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-10 00:10:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "entities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_entities_type"), "entities", ["type"], unique=False)
    # Existing leads get an empty delivery log; the default is only for them
    op.add_column(
        "leads",
        sa.Column(
            "deliveries",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.alter_column("leads", "deliveries", server_default=None)


def downgrade() -> None:
    op.drop_column("leads", "deliveries")
    op.drop_index(op.f("ix_entities_type"), table_name="entities")
    op.drop_table("entities")
