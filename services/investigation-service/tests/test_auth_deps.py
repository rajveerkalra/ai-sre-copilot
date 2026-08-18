"""Auth/RBAC regression test.

app.deps bakes settings.auth_enabled into make_get_principal() at import
time (same pattern remediation-service already uses), so flipping
AUTH_ENABLED via monkeypatch after the app is imported doesn't retroactively
change the dependency's behavior. Instead of fighting that cache, this
exercises the same libs.common.auth functions the real routes depend on,
built with auth_enabled=True explicitly -- a direct test of the security
boundary itself: no token is rejected, a viewer can read but not write, an
operator can do both, and the internal service token authenticates as a
service principal.
"""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from libs.common.auth import Role, create_access_token, make_get_principal, require_permissions

JWT_SECRET = "test-secret-min-32-characters-long!!"
JWT_ISSUER = "ai-sre-copilot-test"


def _make_test_app() -> FastAPI:
    app = FastAPI()
    get_principal = make_get_principal(
        auth_enabled=True,
        jwt_secret=JWT_SECRET,
        jwt_algorithm="HS256",
        jwt_issuer=JWT_ISSUER,
        internal_service_token="test-internal-token",
    )
    require_read = require_permissions(get_principal, "investigations:read")
    require_write = require_permissions(get_principal, "investigations:write")

    @app.get("/read")
    async def read_route(_=Depends(require_read)):
        return {"ok": True}

    @app.post("/write")
    async def write_route(_=Depends(require_write)):
        return {"ok": True}

    return app


@pytest.fixture
def client():
    return TestClient(_make_test_app())


def _token(role: str) -> str:
    return create_access_token(
        subject=f"test-{role}",
        roles=[role],
        secret=JWT_SECRET,
        algorithm="HS256",
        issuer=JWT_ISSUER,
    )


def test_no_token_rejected(client):
    assert client.get("/read").status_code == 401
    assert client.post("/write").status_code == 401


def test_viewer_can_read_not_write(client):
    headers = {"Authorization": f"Bearer {_token(Role.VIEWER.value)}"}
    assert client.get("/read", headers=headers).status_code == 200
    assert client.post("/write", headers=headers).status_code == 403


def test_operator_can_read_and_write(client):
    headers = {"Authorization": f"Bearer {_token(Role.OPERATOR.value)}"}
    assert client.get("/read", headers=headers).status_code == 200
    assert client.post("/write", headers=headers).status_code == 200


def test_admin_can_read_and_write(client):
    headers = {"Authorization": f"Bearer {_token(Role.ADMIN.value)}"}
    assert client.get("/read", headers=headers).status_code == 200
    assert client.post("/write", headers=headers).status_code == 200


def test_service_token_authenticates_as_service_mesh(client):
    headers = {"X-Service-Token": "test-internal-token"}
    assert client.get("/read", headers=headers).status_code == 200
    assert client.post("/write", headers=headers).status_code == 200


def test_wrong_service_token_rejected(client):
    headers = {"X-Service-Token": "not-the-right-token"}
    assert client.get("/read", headers=headers).status_code == 401


def test_garbage_bearer_token_rejected(client):
    headers = {"Authorization": "Bearer not-a-real-jwt"}
    assert client.get("/read", headers=headers).status_code == 401
