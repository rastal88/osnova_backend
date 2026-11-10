"""account: user name, sessions valid after

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-10 14:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("name", sa.String(length=100), nullable=True))
    op.add_column("users", sa.Column("sessions_valid_after", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "sessions_valid_after")
    op.drop_column("users", "name")
