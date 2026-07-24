# High Memory — Sample App

## Symptoms
- `sample_app_memory_ballast_bytes` elevated
- Alert: `SampleAppMemoryFaultActive`

## Mitigation
```bash
curl -X POST http://localhost:8080/faults/memory_leak/deactivate
```
