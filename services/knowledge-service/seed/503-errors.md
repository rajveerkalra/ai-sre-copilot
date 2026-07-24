# 503 Errors / Error Storm

## Symptoms
- Elevated 5xx rate
- Alert SampleAppHighErrorRate
- Logs with order_create_failed / products_list_failed

## Likely root cause
Application error storm — bad deploy, dependency failure, or injected fault.

## Mitigation
1. Correlate with recent deployment
2. Check dependency health
3. Roll back if regression
4. Clear fault injection in demo environments
