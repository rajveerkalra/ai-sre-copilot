# Auth Service (Phase 7)

Issues JWTs with RBAC roles for the platform.

**Port:** 8060

## Demo users (local only)

| User | Password | Role |
|------|----------|------|
| admin | admin123 | admin |
| operator | operator123 | operator |
| viewer | viewer123 | viewer |

## API

- `POST /auth/login` · `POST /api/v1/auth/login`
- `GET /auth/me` (Bearer)
- `/health` `/ready` `/live` `/metrics`
