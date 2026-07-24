# High Latency — Sample App

## Symptoms
- `job:http_request_latency_p99:seconds > 0.5`
- Alert: `SampleAppHighLatency`

## Checks
1. Confirm latency fault: `GET http://localhost:8080/faults`
2. Loki for slow requests: `{service="sample-app"} | json | duration_ms > 500`

## Mitigation
```bash
curl -X POST http://localhost:8080/faults/latency/deactivate
```
