from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_login_and_me(client):
    bad = client.post("/auth/login", json={"username": "admin", "password": "wrong"})
    assert bad.status_code == 401

    ok = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert ok.status_code == 200
    token = ok.json()["access_token"]
    assert token

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    body = me.json()
    assert body["username"] == "admin"
    assert "admin" in body["roles"]


def test_api_v1_login(client):
    res = client.post("/api/v1/auth/login", json={"username": "viewer", "password": "viewer123"})
    assert res.status_code == 200
    assert "viewer" in res.json()["roles"]
