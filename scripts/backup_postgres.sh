#!/usr/bin/env bash
# Daily Postgres logical backup for Tara Gold.
# Usage (cron example):
#   15 2 * * * /opt/taragold/scripts/backup_postgres.sh >> /var/log/taragold-backup.log 2>&1
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups/postgres}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$BACKUP_DIR/taragold_$STAMP.dump"

mkdir -p "$BACKUP_DIR"

if [[ -f "$ROOT_DIR/.env" ]]; then
  # shellcheck disable=SC1091
  set -a
  # Export only simple KEY=VALUE lines
  while IFS= read -r line; do
    [[ -z "$line" || "$line" =~ ^# ]] && continue
    export "$line"
  done < "$ROOT_DIR/.env"
  set +a
fi

: "${POSTGRES_DB:=taragold}"
: "${POSTGRES_USER:=taragold}"
: "${POSTGRES_HOST:=localhost}"
: "${POSTGRES_PORT:=5432}"

if [[ -z "${POSTGRES_PASSWORD:-}" ]]; then
  echo "POSTGRES_PASSWORD is required" >&2
  exit 1
fi

export PGPASSWORD="$POSTGRES_PASSWORD"
pg_dump \
  --host="$POSTGRES_HOST" \
  --port="$POSTGRES_PORT" \
  --username="$POSTGRES_USER" \
  --format=custom \
  --file="$OUT" \
  "$POSTGRES_DB"

echo "Wrote $OUT"
find "$BACKUP_DIR" -type f -name 'taragold_*.dump' -mtime +"$RETENTION_DAYS" -delete
echo "Retention applied (${RETENTION_DAYS}d)"
