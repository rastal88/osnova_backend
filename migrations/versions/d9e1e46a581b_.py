"""empty message

Revision ID: d9e1e46a581b
Revises: ea0b199d8235
Create Date: 2025-04-09 12:11:15.722007

"""
from typing import Sequence, Union


from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9e1e46a581b'
down_revision: Union[str, None] = 'ea0b199d8235'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM users")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.add_column('users', sa.Column('date_created', sa.DateTime(), nullable=True))

    op.execute("ALTER TABLE users ALTER COLUMN id DROP DEFAULT")
    op.execute("ALTER TABLE users ALTER COLUMN id TYPE UUID USING uuid_generate_v4()")
    op.execute("ALTER TABLE users ALTER COLUMN id SET DEFAULT uuid_generate_v4()")


def downgrade() -> None:
    # Возврат к INTEGER, удаляем колонку
    op.execute("ALTER TABLE users ALTER COLUMN id DROP DEFAULT")
    op.execute("ALTER TABLE users ALTER COLUMN id TYPE INTEGER USING id::integer")
    op.drop_column('users', 'date_created')
