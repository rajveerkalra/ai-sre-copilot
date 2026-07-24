#!/usr/bin/env bash
# Generate steady traffic against the sample app
set -euo pipefail

BASE_URL="${SAMPLE_APP_URL:-http://localhost:8080}"
RATE="${RATE:-2}"
DURATION="${DURATION:-60}"

echo "Generating traffic against ${BASE_URL} for ${DURATION}s at ~${RATE} req/s"

end=$((SECONDS + DURATION))
while (( SECONDS < end )); do
  curl -sf -X POST "${BASE_URL}/api/orders" \
    -H 'Content-Type: application/json' \
    -d '{"sku":"SKU-100","quantity":1}' >/dev/null || true
  curl -sf "${BASE_URL}/api/products" >/dev/null || true
  sleep "$(awk "BEGIN {print 1/${RATE}}")"
done

echo "Done."
