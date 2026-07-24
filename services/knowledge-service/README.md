# Knowledge Service (Phase 4)

Runbook upload + semantic search. Embeddings are produced exclusively by
**embedding-gateway** — this service never imports ONNX or Sentence Transformers.

## APIs

| Method | Path | Description |
|--------|------|-------------|
| POST | `/documents` | Upsert runbook |
| GET | `/documents` | List indexed docs |
| DELETE | `/documents/{id}` | Delete doc |
| POST | `/search` | Semantic search (Redis-cached) |

## Config

| Env | Default |
|-----|---------|
| `EMBEDDING_GATEWAY_URL` | `http://embedding-gateway:8041` |
| `REDIS_URL` | `redis://redis:6379/0` |
| `CACHE_ENABLED` | `true` |

## Tests

```bash
cd services/knowledge-service
pip install -r requirements.txt
pytest -q
```
