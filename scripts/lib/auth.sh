#!/usr/bin/env bash
# Shared auth helpers for validation scripts
auth_login() {
  local user="${1:-operator}"
  local pass="${2:-operator123}"
  curl -sf -X POST "http://localhost:8060/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"username\":\"$user\",\"password\":\"$pass\"}" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])"
}

auth_header() {
  local token
  token="$(auth_login "$@")"
  echo "Authorization: Bearer ${token}"
}

service_header() {
  echo "X-Service-Token: ${INTERNAL_SERVICE_TOKEN:-local-internal-service-token}"
}
