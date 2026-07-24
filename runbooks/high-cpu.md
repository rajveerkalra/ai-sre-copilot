# High CPU — Sample App

## Symptoms
- `sample_app_cpu_burn_active == 1`
- Alert: `SampleAppCPUFaultActive`

## Mitigation
```bash
curl -X POST http://localhost:8080/faults/cpu_spike/deactivate
```
