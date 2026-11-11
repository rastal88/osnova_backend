"""encrypt secrets: channel tokens and OAuth tokens are stored encrypted

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-12 10:00:00

"""

from collections.abc import Callable, Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Secret parameters of the entity types the template ships with at this revision;
# types added later are encrypted from the start
ENTITY_SECRETS = {"lead_telegram": ("bot_token",), "lead_webhook": ("secret",)}

entities = sa.table(
    "entities",
    sa.column("id", sa.Uuid()),
    sa.column("type", sa.String()),
    sa.column("params", sa.JSON()),
)
oauth_accounts = sa.table(
    "oauth_accounts",
    sa.column("id", sa.Uuid()),
    sa.column("access_token", sa.Text()),
    sa.column("refresh_token", sa.Text()),
)


def _convert(change: Callable[[str], str]) -> None:
    """Apply `change` to every stored secret; nothing is imported without rows to change."""
    bind = op.get_bind()
    rows = bind.execute(
        sa.select(entities).where(entities.c.type.in_(list(ENTITY_SECRETS)))
    ).all()
    for row in rows:
        params = dict(row.params or {})
        for key in ENTITY_SECRETS[row.type]:
            if params.get(key):
                params[key] = change(params[key])
        if params != row.params:
            bind.execute(entities.update().where(entities.c.id == row.id).values(params=params))

    for row in bind.execute(sa.select(oauth_accounts)).all():
        values = {
            "access_token": change(row.access_token),
            "refresh_token": change(row.refresh_token) if row.refresh_token else None,
        }
        bind.execute(oauth_accounts.update().where(oauth_accounts.c.id == row.id).values(values))


def _cipher(name: str) -> Callable[[str], str]:
    # Imported only here: a database without the auth module has no cryptography
    from app.modules.auth import encryption

    return getattr(encryption, name)


def upgrade() -> None:
    # An encrypted token is longer than the plain one
    op.alter_column("oauth_accounts", "access_token", type_=sa.Text(), existing_nullable=False)
    op.alter_column("oauth_accounts", "refresh_token", type_=sa.Text(), existing_nullable=True)
    if _has_secrets():
        _convert(_cipher("encrypt"))


def downgrade() -> None:
    if _has_secrets():
        _convert(_cipher("decrypt"))
    op.alter_column(
        "oauth_accounts", "refresh_token", type_=sa.String(length=1024), existing_nullable=True
    )
    op.alter_column(
        "oauth_accounts", "access_token", type_=sa.String(length=1024), existing_nullable=False
    )


def _has_secrets() -> bool:
    bind = op.get_bind()
    count = sa.select(sa.func.count())
    channels = bind.scalar(
        count.select_from(entities).where(entities.c.type.in_(list(ENTITY_SECRETS)))
    )
    return bool(channels or bind.scalar(count.select_from(oauth_accounts)))
