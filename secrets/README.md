# Secrets management (Phase 7)

Keep runtime secrets out of git.

1. `cp secrets/secrets.example.env secrets/.env.secrets`
2. Edit values; `chmod 600 secrets/.env.secrets`
3. Compose loads shared JWT / DB password via `.env` (root) — prefer sourcing secrets into `.env` for local, or K8s Secrets / External Secrets Operator in production.

Never commit `secrets/.env.secrets` or rotate keys after a leak.
