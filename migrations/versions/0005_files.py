"""files

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-10 00:40:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index(op.f("ix_files_created_at"), "files", ["created_at"], unique=False)
    op.create_index(op.f("ix_files_owner_id"), "files", ["owner_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_files_owner_id"), table_name="files")
    op.drop_index(op.f("ix_files_created_at"), table_name="files")
    op.drop_table("files")
