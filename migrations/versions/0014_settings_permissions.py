"""settings permissions: settings.manage becomes one permission per settings group

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-12 12:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD = "settings.manage"
# The settings groups of the template at this revision
NEW = [
    "settings.site",
    "settings.languages",
    "settings.mail",
    "settings.protection",
    "settings.retention",
    "settings.files",
    "settings.notifications",
]

roles = sa.table("roles", sa.column("slug", sa.String()), sa.column("permissions", sa.JSON()))


def _replace(old: list[str], new: list[str]) -> None:
    bind = op.get_bind()
    for row in bind.execute(sa.select(roles)).all():
        permissions = list(row.permissions or [])
        if not set(old) & set(permissions):
            continue
        kept = [name for name in permissions if name not in old]
        updated = sorted({*kept, *new})
        bind.execute(roles.update().where(roles.c.slug == row.slug).values(permissions=updated))


def upgrade() -> None:
    # Whoever could change the settings can change every group
    _replace([OLD], NEW)


def downgrade() -> None:
    # Any settings group was enough to change them all before
    _replace(NEW, [OLD])
