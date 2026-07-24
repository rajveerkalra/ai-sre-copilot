# Dependency Timeout — Sample App

## Symptoms
- `sample_app_dependency_calls_total{status="timeout"}` increasing
- HTTP 504 on `POST /api/orders`
- Alert: `SampleAppDependencyTimeouts`

## Mitigation
```bash
curl -X POST http://localhost:8080/faults/dependency_timeout/deactivate
```
