# Deployment Rollback

## Symptoms
- Error/latency spike shortly after rollout
- New image revision preceding incident
- ReplicaSet change before alert startsAt

## Likely root cause
Deployment regression.

## Mitigation
1. `kubectl rollout undo deployment/<name>`
2. Verify error rate returns to baseline
3. Quarantine bad image tag
