#!/usr/bin/env bash
# Restore Postgres from a gzipped pg_dump. DANGEROUS — overwrites data.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

FILE="${1:-}"
if [[ -z "$FILE" || ! -f "$FILE" ]]; then
  echo "Usage: $0 backups/sre_incidents_YYYYMMDDTHHMMSSZ.sql.gz"
  exit 1
fi

echo "WARNING: This replaces database ${POSTGRES_DB:-sre_incidents}."
read -r -p "Type RESTORE to continue: " confirm
[[ "$confirm" == "RESTORE" ]] || { echo "Aborted"; exit 1; }

gunzip -c "$FILE" | docker compose exec -T postgres \
  psql -U "${POSTGRES_USER:-sre}" -d "${POSTGRES_DB:-sre_incidents}"
echo "OK restore complete from $FILE"
