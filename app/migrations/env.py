from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import os
import sys

# Добавляем путь к проекту в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))


# Импортируем настройки из config.py
from app.core.config import settings

# Конфигурация Alembic
config = context.config

# Переопределяем sqlalchemy.url
config.set_main_option('sqlalchemy.url', settings.DATABASE_URL)

# Настройка логгера
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Подключаем модели
from app.db.base import Base  # Импортируем Base из вашего проекта
target_metadata = Base.metadata

def run_migrations_offline():
    """Запуск миграций в offline-режиме."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """Запуск миграций в online-режиме."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()