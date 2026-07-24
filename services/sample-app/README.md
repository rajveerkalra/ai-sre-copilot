# Sample Application — Phase 1

Demo FastAPI workload that generates metrics, structured logs, and controllable
faults so the observability stack and (later) the AI investigation pipeline can
be exercised end-to-end.

## Endpoints

| Path | Purpose |
|------|---------|
| `GET /healthz` | Liveness/health |
| `GET /livez` | Kubernetes liveness |
| `GET /readyz` | Kubernetes readiness |
| `GET /metrics` | Prometheus scrape |
| `GET /api/info` | Service metadata |
| `GET /api/products` | List products |
| `POST /api/orders` | Create order (business traffic) |
| `GET /faults` | Fault injection status + scenarios |
| `POST /faults/{type}/activate` | Activate a fault |
| `POST /faults/{type}/deactivate` | Deactivate a fault |
| `POST /faults/deactivate-all` | Clear all faults |

## Fault types

- `error_storm` — elevate 5xx rate
- `latency` — inject request delay
- `cpu_spike` — background CPU burn
- `memory_leak` — allocate ballast
- `dependency_timeout` — payments dependency hangs
- `crash` — soft (HTTP 500) or hard (`os._exit`) crash

## Local run (without Compose)

```bash
cd services/sample-app
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=../..:../../libs:. uvicorn app.main:app --reload --port 8080
```

## Tests

```bash
cd services/sample-app
pip install -r requirements.txt
PYTHONPATH=../..:. pytest -q
```
