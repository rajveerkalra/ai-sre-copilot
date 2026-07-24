# CrashLoopBackOff

## Symptoms
- Pod repeatedly restarts
- Container state waiting reason CrashLoopBackOff
- High restart_count

## Likely root cause
Application startup failure — crash on boot, bad config, missing dependency, or failed health checks.

## Mitigation
1. Inspect `kubectl logs --previous`
2. Verify config / secrets / env
3. Check image tag and recent deployment
4. Roll back if deployment-correlated
