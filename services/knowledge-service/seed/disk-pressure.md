# Disk Pressure

## Symptoms
- Node condition DiskPressure=True
- Evicted pods
- Failed writes / disk full logs

## Likely root cause
Node ephemeral storage exhausted.

## Mitigation
1. Clear unused images/logs
2. Expand disk
3. Cordon/drain if needed
