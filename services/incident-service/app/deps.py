"""Auth dependencies for incident-service."""

from __future__ import annotations

from libs.common.auth import make_get_principal, require_permissions

from app.config import get_settings

_settings = get_settings()

get_principal = make_get_principal(
    auth_enabled=_settings.auth_enabled,
    jwt_secret=_settings.jwt_secret,
    jwt_algorithm=_settings.jwt_algorithm,
    jwt_issuer=_settings.jwt_issuer,
    internal_service_token=_settings.internal_service_token or None,
)

require_read = require_permissions(get_principal, "incidents:read")
require_write = require_permissions(get_principal, "incidents:write")
