# API Documentation

All HTTP services expose interactive OpenAPI at `/docs` (Swagger UI) and `/openapi.json`.

| Service | Port | OpenAPI | Primary purpose |
|---------|-----:|---------|-----------------|
| sample-app | 8080 | http://localhost:8080/docs | Demo workload + fault injection |
| incident-service | 8000 | http://localhost:8000/docs | Webhooks, incidents, timeline |
| context-service | 8020 | http://localhost:8020/docs | Evidence collection |
| knowledge-service | 8030 | http://localhost:8030/docs | Runbook search |
| investigation-service | 8031 | http://localhost:8031/docs | LangGraph RCA |
| remediation-service | 8032 | http://localhost:8032/docs | Propose / approve / execute |
| model-gateway | 8040 | http://localhost:8040/docs | LLM provider abstraction |
| embedding-gateway | 8041 | http://localhost:8041/docs | Embedding provider abstraction |
| executive-dashboard | 8050 | — | React UI (proxies APIs) |
| auth-service | 8060 | http://localhost:8060/docs | JWT login + `/auth/me` |

## Versioning

Legacy paths remain. Prefer `/api/v1/...` where available (auth, incidents, remediations).

## Auth

```bash
TOKEN=$(curl -sf -X POST http://localhost:8060/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"operator","password":"operator123"}' | jq -r .access_token)

curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/incidents?page_size=5 | jq
```

Roles: `viewer` (read), `operator` (propose/approve/execute), `admin` (all).

Mesh: `X-Service-Token: $INTERNAL_SERVICE_TOKEN`.

## Export OpenAPI (CI / clients)

```bash
for s in 8000 8020 8030 8031 8032 8040 8041 8060; do
  curl -sf "http://localhost:$s/openapi.json" -o "openapi-$s.json" || true
done
```
