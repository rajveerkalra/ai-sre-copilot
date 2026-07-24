# Runbook — Authentication & RBAC (Phase 7)

## Symptoms

- API returns `401 Bearer token required`
- Dashboard redirects to `/login`
- Mesh calls fail with 401

## Checks

```bash
curl -s http://localhost:8060/ready | jq
curl -s -X POST http://localhost:8060/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"operator","password":"operator123"}' | jq
```

## Fix paths

1. **Wrong password** — use demo users or update `AUTH_USERS`
2. **JWT_SECRET mismatch** — auth-service and incident/remediation must share the same secret
3. **Clock skew** — token `exp` invalid; sync container time
4. **Service calls** — set `X-Service-Token: $INTERNAL_SERVICE_TOKEN`
5. **Disable auth (break-glass)** — set `AUTH_ENABLED=false` and recreate services (local only)

## Rotate JWT secret

1. Generate new secret (≥32 chars)
2. Update `.env` `JWT_SECRET`
3. `docker compose up -d --force-recreate auth-service incident-service remediation-service`
4. Force all users to re-login
