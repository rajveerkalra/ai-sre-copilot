# Node Not Ready

## Symptoms
- Node Ready=False
- Pods Pending / Unknown
- Kubelet / network issues

## Likely root cause
Node failure or kubelet not ready.

## Mitigation
1. Check node conditions and kubelet logs
2. Drain and replace node
3. Reschedule workloads
