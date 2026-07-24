"""Auth / RBAC dependencies for remediation-service."""

from __future__ import annotations

from libs.common.auth import make_get_principal, require_permissions
from libs.common.ratelimit import SlidingWindowRateLimiter, make_rate_limit_dependency

from app.config import get_settings

_settings = get_settings()

get_principal = make_get_principal(
    auth_enabled=_settings.auth_enabled,
    jwt_secret=_settings.jwt_secret,
    jwt_algorithm=_settings.jwt_algorithm,
    jwt_issuer=_settings.jwt_issuer,
    internal_service_token=_settings.internal_service_token or None,
)

require_read = require_permissions(get_principal, "remediations:read")
require_propose = require_permissions(get_principal, "remediations:propose")
require_approve = require_permissions(get_principal, "remediations:approve")
require_execute = require_permissions(get_principal, "remediations:execute")

mutate_limiter = SlidingWindowRateLimiter(max_requests=60, window_seconds=60)
rate_limit_mutate = make_rate_limit_dependency(mutate_limiter)
