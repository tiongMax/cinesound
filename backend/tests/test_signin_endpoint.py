"""POST /signin tests with Google tokeninfo mocked via respx + memory migrate stubbed."""

from unittest.mock import AsyncMock

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.db import _pool_dep
from app.main import app
from app.routes import signin as signin_mod
from app.routes.signin import TOKENINFO_URL


@pytest.fixture
def fake_pool():
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=None)
    pool.fetch = AsyncMock(return_value=[])
    pool.execute = AsyncMock(return_value="INSERT 0 4")
    return pool


@pytest.fixture
def client(fake_pool, monkeypatch):
    app.dependency_overrides[_pool_dep] = lambda: fake_pool
    monkeypatch.setattr(signin_mod.settings, "google_client_id", "client-id-123")
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@respx.mock
def test_signin_returns_500_when_not_configured(client, monkeypatch):
    monkeypatch.setattr(signin_mod.settings, "google_client_id", None)
    r = client.post("/signin", json={"id_token": "t"})
    assert r.status_code == 500


@respx.mock
def test_signin_rejects_missing_token(client):
    r = client.post("/signin", json={})
    assert r.status_code == 400


@respx.mock
def test_signin_rejects_bad_token(client):
    respx.get(TOKENINFO_URL).mock(return_value=httpx.Response(400, json={"error": "bad"}))
    r = client.post("/signin", json={"id_token": "bad"})
    assert r.status_code == 401


@respx.mock
def test_signin_rejects_wrong_audience(client):
    respx.get(TOKENINFO_URL).mock(
        return_value=httpx.Response(200, json={"aud": "other-client", "sub": "u1"})
    )
    r = client.post("/signin", json={"id_token": "t"})
    assert r.status_code == 401


@respx.mock
def test_signin_migrates_memory_and_returns_user_id(client, fake_pool):
    respx.get(TOKENINFO_URL).mock(
        return_value=httpx.Response(200, json={"aud": "client-id-123", "sub": "u1"})
    )
    r = client.post(
        "/signin",
        json={"id_token": "t"},
        cookies={"session_id": "session:abc"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == "google:u1"
    assert body["migrated_keys"] == 4  # from "INSERT 0 4"


@respx.mock
def test_signin_without_session_cookie_migrates_zero(client):
    respx.get(TOKENINFO_URL).mock(
        return_value=httpx.Response(200, json={"aud": "client-id-123", "sub": "u1"})
    )
    r = client.post("/signin", json={"id_token": "t"})
    assert r.status_code == 200
    assert r.json()["migrated_keys"] == 0
