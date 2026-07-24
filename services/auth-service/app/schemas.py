from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    roles: list[str]
    username: str


class MeResponse(BaseModel):
    username: str
    roles: list[str]
    email: str | None = None
    name: str | None = None
    permissions: list[str]
