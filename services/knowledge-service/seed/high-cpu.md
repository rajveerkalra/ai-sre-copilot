# High CPU

## Symptoms
- Elevated `cpu_usage` / container CPU throttling
- Rising latency under load
- Alert: HighCPU / CPUSaturation

## Investigation
1. Confirm metric evidence for CPU saturation
2. Correlate with recent deployment
3. Check for CPU fault injection / runaway loops
4. Inspect top processes / profiling if available

## Mitigation
- Scale horizontally
- Limit CPU-intensive jobs
- Roll back if post-deploy regression
