# Embedding Gateway

Provider-abstracted embeddings.

- Providers: `onnx` (default), `sentence_transformers` (optional dep), `openai` (stub)
- Redis cache keyed by text hash
- Metrics: `embedding_latency_seconds`, `cache_hit_ratio`, `provider_failures_total`

```bash
curl -s -X POST http://localhost:8041/v1/embed \
  -H 'Content-Type: application/json' \
  -d '{"texts":["high CPU saturation"]}' | jq '.dimensions,.provider,.cached'
```

Knowledge Service is the only Chroma client; it never embeds locally.
