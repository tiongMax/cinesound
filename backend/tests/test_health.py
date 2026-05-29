"""Smoke test: app boots without a DATABASE_URL and /health returns ok."""

from fastapi.testclient import TestClient

from app.main import app


def test_health_without_db():
    with TestClient(app) as client:
        r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] is False
