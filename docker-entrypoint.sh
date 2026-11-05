#!/bin/sh
set -e

if [ "${RUN_MIGRATIONS:-false}" = "true" ] && [ -n "${DATABASE_URL:-}" ]; then
  echo "Running database migrations (alembic upgrade head)..."
  alembic upgrade head
fi

exec "$@"
