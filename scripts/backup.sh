#!/bin/sh
# Back up the Docker Compose stack into backups/ (`make backup`):
#   osnova-<date>.dump          the PostgreSQL database (pg_dump, custom format)
#   osnova-<date>-files.tar.gz  uploads (FILES_STORAGE=local) and form submissions
#                               (FORMS_DELIVERY=file), when there is anything to keep
# KEEP_DAYS=N deletes backups older than N days afterwards.
set -eu

COMPOSE=${COMPOSE:-docker compose -f docker-compose.yml -f docker-compose.datastores.yml}
DIR=${BACKUP_DIR:-backups}
STAMP=$(date +%Y-%m-%d_%H%M%S)
DB="$DIR/osnova-$STAMP.dump"
FILES="$DIR/osnova-$STAMP-files.tar.gz"

mkdir -p "$DIR"
trap 'rm -f "$DB.part" "$FILES.part"' EXIT

if [ -n "$($COMPOSE ps -q postgres 2>/dev/null)" ]; then
  # shellcheck disable=SC2016  # expanded inside the container
  $COMPOSE exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$DB.part"
  mv "$DB.part" "$DB"
  echo "Database: $DB ($(du -h "$DB" | cut -f1))"
else
  echo "No postgres container (minimal profile?): database skipped"
fi

# A one-off backend container sees the same volumes and .env as the app; it prints
# nothing when the files live elsewhere (S3) and forms are not written to disk
# shellcheck disable=SC2016  # expanded inside the container
$COMPOSE run --rm --no-deps -T --entrypoint sh backend -c '
  dirs=""
  [ "${FILES_STORAGE:-local}" = local ] && [ -n "$(ls -A uploads)" ] && dirs="uploads"
  [ "${FORMS_DELIVERY:-log}" = file ] && [ -n "$(ls -A data)" ] && dirs="$dirs data"
  [ -z "$dirs" ] || tar czf - $dirs
' > "$FILES.part"
if [ -s "$FILES.part" ]; then
  mv "$FILES.part" "$FILES"
  echo "Files: $FILES ($(du -h "$FILES" | cut -f1))"
else
  echo "No local files to keep: files skipped"
fi

if [ -n "${KEEP_DAYS:-}" ]; then
  find "$DIR" -maxdepth 1 -name 'osnova-*' -mtime +"$KEEP_DAYS" -print -delete
fi
