#!/usr/bin/env bash
# Backup Postgres (sre_incidents) to backups/
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p backups
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="backups/sre_incidents_${STAMP}.sql.gz"
echo "==> Dumping postgres → $OUT"
docker compose exec -T postgres pg_dump -U "${POSTGRES_USER:-sre}" "${POSTGRES_DB:-sre_incidents}" \
  | gzip > "$OUT"
echo "OK  $(du -h "$OUT" | awk '{print $1}')"
ls -la "$OUT"
