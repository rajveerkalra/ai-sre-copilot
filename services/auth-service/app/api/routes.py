from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import Settings, get_settings
from app.metrics import LOGIN_TOTAL, TOKEN_ISSUED_TOTAL
from app.schemas import LoginRequest, MeResponse, TokenResponse
from app.users import UserRecord, parse_users, verify_password

from libs.common.audit import emit_audit
from libs.common.auth import (
    PERMISSIONS,
    Principal,
    Role,
    create_access_token,
    make_get_principal,
)
from libs.common.ratelimit import SlidingWindowRateLimiter, make_rate_limit_dependency

router = APIRouter()
_users_cache: dict[str, UserRecord] | None = None
_login_limiter = SlidingWindowRateLimiter(max_requests=30, window_seconds=60)

_settings = get_settings()
get_principal = make_get_principal(
    auth_enabled=True,
    jwt_secret=_settings.jwt_secret,
    jwt_algorithm=_settings.jwt_algorithm,
    jwt_issuer=_settings.jwt_issuer,
)


def get_users(settings: Settings = Depends(get_settings)) -> dict[str, UserRecord]:
    global _users_cache
    if _users_cache is None:
        _users_cache = parse_users(settings)
    return _users_cache


def _permissions_for(roles: list[str]) -> list[str]:
    perms: set[str] = set()
    for role in roles:
        if role == Role.ADMIN.value:
            return ["*"]
        perms |= PERMISSIONS.get(role, set())
    return sorted(perms)


@router.post("/auth/login", response_model=TokenResponse)
@router.post("/api/v1/auth/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    settings: Settings = Depends(get_settings),
    users: dict[str, UserRecord] = Depends(get_users),
    _: None = Depends(make_rate_limit_dependency(_login_limiter)),
) -> TokenResponse:
    user = users.get(body.username)
    if user is None or not verify_password(body.password, user.password_hash):
        LOGIN_TOTAL.labels(result="failure").inc()
        emit_audit(
            action="auth.login",
            actor=body.username,
            resource_type="user",
            resource_id=body.username,
            outcome="failure",
            service=settings.service_name,
            detail={"reason": "invalid_credentials"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = create_access_token(
        subject=user.username,
        roles=user.roles,
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expires_minutes=settings.access_token_ttl_minutes,
        email=user.email,
        name=user.name,
        issuer=settings.jwt_issuer,
    )
    LOGIN_TOTAL.labels(result="success").inc()
    TOKEN_ISSUED_TOTAL.inc()
    emit_audit(
        action="auth.login",
        actor=user.username,
        resource_type="user",
        resource_id=user.username,
        outcome="success",
        service=settings.service_name,
        detail={"roles": user.roles},
    )
    return TokenResponse(
        access_token=token,
        expires_in=settings.access_token_ttl_minutes * 60,
        roles=user.roles,
        username=user.username,
    )


@router.get("/auth/me", response_model=MeResponse)
@router.get("/api/v1/auth/me", response_model=MeResponse)
async def me(principal: Principal = Depends(get_principal)) -> MeResponse:
    return MeResponse(
        username=principal.sub,
        roles=principal.roles,
        email=principal.email,
        name=principal.name,
        permissions=_permissions_for(principal.roles),
    )


@router.get("/health")
@router.get("/healthz")
async def health(settings: Settings = Depends(get_settings)) -> dict:
    return {
        "status": "healthy",
        "service": settings.service_name,
        "version": settings.version,
    }


@router.get("/ready")
@router.get("/readyz")
async def ready(
    settings: Settings = Depends(get_settings),
    users: dict[str, UserRecord] = Depends(get_users),
) -> dict:
    if not users:
        return {
            "status": "not_ready",
            "service": settings.service_name,
            "reason": "no_users",
        }
    return {"status": "ready", "service": settings.service_name, "users": len(users)}


@router.get("/live")
@router.get("/livez")
async def live(settings: Settings = Depends(get_settings)) -> dict:
    return {"status": "alive", "service": settings.service_name}
