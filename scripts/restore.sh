#!/bin/sh
# Restore a backup made by `make backup` (`make restore FILE=...`):
#   *.dump    replaces the database with the dump (the database is recreated)
#   *.tar.gz  replaces the uploads / form submissions folders found in the archive
# Asks first; CONFIRM=yes skips the question. The backend, worker and beat are
# stopped meanwhile and started again afterwards.
set -eu

COMPOSE=${COMPOSE:-docker compose -f docker-compose.yml -f docker-compose.datastores.yml}
FILE=${1:-}

case "$FILE" in
  *.dump) WHAT="the database" ;;
  *.tar.gz) WHAT="the uploaded files and form submissions in the archive" ;;
  *) echo "Usage: make restore FILE=backups/osnova-<date>.dump (or -files.tar.gz)"; exit 2 ;;
esac
[ -f "$FILE" ] || { echo "No such file: $FILE"; exit 2; }
if [ "$WHAT" = "the database" ] && [ -z "$($COMPOSE ps -q postgres 2>/dev/null)" ]; then
  echo "The postgres container is not running: start the stack first (make up-standard)"
  exit 1
fi

if [ "${CONFIRM:-}" != "yes" ]; then
  echo "This replaces $WHAT with $FILE."
  echo "Current data is lost (make backup first to keep it)."
  printf "Type yes to continue: "
  read -r answer
  [ "$answer" = "yes" ] || { echo "Cancelled"; exit 1; }
fi

# Stop what writes to the data, and start it again however the restore ends
RUNNING=$($COMPOSE ps --services --status running | grep -E '^(backend|worker|beat)$' || true)
if [ -n "$RUNNING" ]; then
  # shellcheck disable=SC2086  # one argument per service
  $COMPOSE stop $RUNNING
  # shellcheck disable=SC2086
  trap '$COMPOSE start $RUNNING' EXIT
fi

if [ "$WHAT" = "the database" ]; then
  # A fresh database, so tables added after the backup do not stay behind
  # shellcheck disable=SC2016  # expanded inside the container
  $COMPOSE exec -T postgres sh -c '
    set -e
    dropdb -U "$POSTGRES_USER" --if-exists --force "$POSTGRES_DB"
    createdb -U "$POSTGRES_USER" "$POSTGRES_DB"
    pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --exit-on-error
  ' < "$FILE"
  echo "Database restored from $FILE (run make migrate if the backup is older than the code)"
else
  # shellcheck disable=SC2016  # expanded inside the container
  $COMPOSE run --rm --no-deps -T --entrypoint sh backend -c '
    set -e
    tmp=$(mktemp -d)
    tar xzf - -C "$tmp"
    for dir in uploads data; do
      [ -d "$tmp/$dir" ] || continue
      find "$dir" -mindepth 1 -delete
      cp -a "$tmp/$dir/." "$dir/"
      echo "Restored $dir"
    done
    rm -rf "$tmp"
  ' < "$FILE"
fi
