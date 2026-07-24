# High Latency

## Symptoms
- Elevated p95/p99 latency
- Timeout increase
- Alert: HighLatency

## Investigation
1. Cite latency metric evidence
2. Check dependency timeouts in logs
3. Correlate with deployment

## Mitigation
- Identify slow dependency
- Temporary timeout/circuit breaker
- Roll back performance regression
