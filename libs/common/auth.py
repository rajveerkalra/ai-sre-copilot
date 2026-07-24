"""JWT authentication and RBAC helpers for AI SRE Copilot services."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Iterable

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=False)


class Role(str, Enum):
    VIEWER = "viewer"
    OPERATOR = "operator"
    ADMIN = "admin"


# Permission catalog
PERMISSIONS: dict[str, set[str]] = {
    Role.VIEWER: {
        "incidents:read",
        "remediations:read",
        "investigations:read",
        "context:read",
        "audit:read",
    },
    Role.OPERATOR: {
        "incidents:read",
        "incidents:write",
        "remediations:read",
        "remediations:propose",
        "remediations:approve",
        "remediations:execute",
        "investigations:read",
        "investigations:write",
        "context:read",
        "context:write",
        "audit:read",
    },
    Role.ADMIN: {"*"},
}


@dataclass
class Principal:
    sub: str
    roles: list[str] = field(default_factory=list)
    email: str | None = None
    name: str | None = None
    token_id: str | None = None

    def has_role(self, role: str) -> bool:
        return role in self.roles or Role.ADMIN.value in self.roles

    def has_permission(self, permission: str) -> bool:
        for role in self.roles:
            perms = PERMISSIONS.get(role, set())
            if "*" in perms or permission in perms:
                return True
        return False


def create_access_token(
    *,
    subject: str,
    roles: Iterable[str],
    secret: str,
    algorithm: str = "HS256",
    expires_minutes: int = 60,
    email: str | None = None,
    name: str | None = None,
    issuer: str = "ai-sre-copilot",
    extra: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "roles": list(roles),
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
        "iss": issuer,
    }
    if email:
        payload["email"] = email
    if name:
        payload["name"] = name
    if extra:
        payload.update(extra)
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_token(
    token: str,
    *,
    secret: str,
    algorithm: str = "HS256",
    issuer: str = "ai-sre-copilot",
) -> Principal:
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[algorithm],
            issuer=issuer,
            options={"require": ["exp", "sub", "iss"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    roles = payload.get("roles") or []
    if isinstance(roles, str):
        roles = [roles]
    return Principal(
        sub=str(payload["sub"]),
        roles=[str(r) for r in roles],
        email=payload.get("email"),
        name=payload.get("name"),
        token_id=payload.get("jti"),
    )


def make_get_principal(
    *,
    auth_enabled: bool,
    jwt_secret: str,
    jwt_algorithm: str = "HS256",
    jwt_issuer: str = "ai-sre-copilot",
    anonymous_roles: list[str] | None = None,
    internal_service_token: str | None = None,
    service_principal_roles: list[str] | None = None,
) -> Callable:
    """FastAPI dependency factory.

    When auth is disabled, returns an anonymous principal with elevated roles.
    When enabled: accepts Bearer JWT or matching X-Service-Token for mesh calls.
    """

    async def get_principal(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    ) -> Principal:
        if not auth_enabled:
            principal = Principal(
                sub="anonymous",
                roles=anonymous_roles or [Role.ADMIN.value],
                name="anonymous",
            )
            request.state.principal = principal
            return principal

        svc_token = request.headers.get("x-service-token")
        if (
            internal_service_token
            and svc_token
            and svc_token == internal_service_token
        ):
            principal = Principal(
                sub="service-mesh",
                roles=service_principal_roles or [Role.OPERATOR.value, Role.ADMIN.value],
                name="service-mesh",
            )
            request.state.principal = principal
            return principal

        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Bearer token required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        principal = decode_token(
            credentials.credentials,
            secret=jwt_secret,
            algorithm=jwt_algorithm,
            issuer=jwt_issuer,
        )
        request.state.principal = principal
        return principal

    return get_principal


def require_permissions(get_principal: Callable, *permissions: str):
    """FastAPI dependency requiring ALL listed permissions."""

    async def dependency(
        principal: Principal = Depends(get_principal),
    ) -> Principal:
        missing = [p for p in permissions if not principal.has_permission(p)]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permissions: {', '.join(missing)}",
            )
        return principal

    return dependency


def require_roles(get_principal: Callable, *roles: str):
    async def dependency(
        principal: Principal = Depends(get_principal),
    ) -> Principal:
        if any(principal.has_role(r) for r in roles) or principal.has_role(Role.ADMIN.value):
            return principal
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires one of roles: {', '.join(roles)}",
        )

    return dependency
