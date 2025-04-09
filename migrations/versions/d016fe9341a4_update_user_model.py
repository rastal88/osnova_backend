"""<update user model>

Revision ID: d016fe9341a4
Revises: b924cb046f66
Create Date: 2025-04-02 15:34:03.839986

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd016fe9341a4'
down_revision: Union[str, None] = 'b924cb046f66'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Сначала создаём тип ENUM
    role_enum = postgresql.ENUM('USER', 'ADMIN', 'MODERATOR', name='role')
    role_enum.create(op.get_bind())

    # Затем добавляем колонку с этим типом
    op.add_column('users', sa.Column('role', role_enum, nullable=False, server_default='USER'))


def downgrade() -> None:
    # Сначала удаляем колонку
    op.drop_column('users', 'role')

    # Затем удаляем тип ENUM
    role_enum = postgresql.ENUM('USER', 'ADMIN', 'MODERATOR', name='role')
    role_enum.drop(op.get_bind())
