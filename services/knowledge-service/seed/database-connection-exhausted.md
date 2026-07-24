# Database Connection Exhausted

## Symptoms
- Connection pool timeouts
- Logs: "too many connections", "connection refused", "OperationalError"
- Elevated dependency timeout metrics

## Likely root cause
Database saturation or connection pool exhaustion.

## Mitigation
1. Scale connection limits / pool size
2. Kill idle sessions
3. Check for connection leaks after deploy
4. Fail over read replicas if applicable
