# OOMKilled — Memory Exhaustion

## Symptoms
- Container terminated with reason `OOMKilled`
- Rising memory usage / ballast metrics
- Sudden restarts after memory climb

## Evidence to collect
- `sample_app_memory_ballast_bytes` or container memory working set
- Kubernetes container last state reason = OOMKilled
- Recent deployment that changed memory limits

## Likely root cause
Memory exhaustion — process exceeded cgroup memory limit.

## Mitigation
1. Increase memory limits / requests
2. Fix memory leak
3. Roll back recent image if regression
4. Restart unhealthy pods after limit adjustment
