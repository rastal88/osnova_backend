"""rename ADMIN to ROOT

Revision ID: dd3279f2842b
Revises: d9e1e46a581b
Create Date: 2025-11-02 17:41:08.095042

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dd3279f2842b'
down_revision: Union[str, None] = 'd9e1e46a581b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Пересоздаём enum тип, так как в PostgreSQL нельзя удалять значения enum
    # Сначала снимаем default значение, чтобы избежать зависимостей от старого enum
    op.alter_column('users', 'role', server_default=None)
    
    # 2. Временно конвертируем роль в TEXT и переименовываем ADMIN в ROOT
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE text USING role::text")
    op.execute("UPDATE users SET role = 'ROOT' WHERE role = 'ADMIN'")
    
    # 3. Удаляем старый тип enum
    op.execute("DROP TYPE role")
    
    # 4. Создаём новый тип enum без ADMIN
    op.execute("CREATE TYPE role AS ENUM ('USER', 'ROOT', 'MODERATOR')")
    
    # 5. Меняем тип колонки обратно на enum и устанавливаем default
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE role USING role::role")
    op.alter_column('users', 'role', server_default='USER')


def downgrade() -> None:
    # Обратная миграция
    # 1. Переименовываем ROOT обратно в ADMIN
    op.execute("UPDATE users SET role = 'ADMIN' WHERE role = 'ROOT'")
    
    # 2. Меняем тип колонки на TEXT
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE text USING role::text")
    
    # 3. Удаляем новый тип enum
    op.execute("DROP TYPE role")
    
    # 4. Создаём старый тип enum с ADMIN
    op.execute("CREATE TYPE role AS ENUM ('USER', 'ADMIN', 'MODERATOR')")
    
    # 5. Меняем тип колонки обратно на enum
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE role USING role::role")
