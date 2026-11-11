"""roles: permissions instead of fixed roles

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-11 15:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# What a moderator could do before this revision; root has every permission in the code
MODERATOR = [
    "admin.access",
    "users.read",
    "users.export",
    "users.block",
    "leads.read",
    "leads.manage",
    "leads.export",
    "files.manage",
]


def upgrade() -> None:
    roles = op.create_table(
        "roles",
        sa.Column("slug", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("system", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("slug"),
    )
    op.bulk_insert(
        roles,
        [
            {"slug": "root", "name": "Root", "permissions": [], "system": True},
            {"slug": "moderator", "name": "Moderator", "permissions": MODERATOR, "system": True},
            {"slug": "user", "name": "User", "permissions": [], "system": True},
        ],
    )
    # The enum stored the names: ROOT, MODERATOR, USER. A database created before the
    # migrations may have a default on the column: it holds the enum type and is not
    # used (the application sets the role).
    op.alter_column(
        "users",
        "role",
        type_=sa.String(length=50),
        existing_nullable=False,
        server_default=None,
        postgresql_using="lower(role::text)",
    )
    sa.Enum(name="role").drop(op.get_bind())
    op.create_foreign_key("users_role_fkey", "users", "roles", ["role"], ["slug"])
    op.create_index("ix_users_role", "users", ["role"])


def downgrade() -> None:
    op.drop_index("ix_users_role", table_name="users")
    op.drop_constraint("users_role_fkey", "users", type_="foreignkey")
    role = sa.Enum("ROOT", "MODERATOR", "USER", name="role")
    role.create(op.get_bind())
    # Roles created in the admin do not exist in the old model
    op.execute("UPDATE users SET role = 'user' WHERE role NOT IN ('root', 'moderator', 'user')")
    op.alter_column(
        "users",
        "role",
        type_=role,
        existing_nullable=False,
        postgresql_using="upper(role)::role",
    )
    op.drop_table("roles")
