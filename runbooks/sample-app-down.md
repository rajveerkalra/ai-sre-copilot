# Sample App Down

## Symptoms
- `up{job="sample-app"} == 0`
- Alert: `SampleAppDown`

## Checks
```bash
docker compose ps sample-app
docker compose logs --tail=100 sample-app
curl -v http://localhost:8080/healthz
```

## Mitigation
```bash
docker compose up -d sample-app
```
