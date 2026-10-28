"""Integration tests for the /health public probe."""

from fastapi.testclient import TestClient


def test_health_endpoint_publicly_accessible(client: TestClient) -> None:
    """Verify that /health does not require authentication and returns a 200 OK with valid schema."""
    resp = client.get("/health")
    assert resp.status_code == 200

    data = resp.json()
    assert data["status"] in ("healthy", "degraded")
    assert data["version"] == "2.0.0"
    assert "timestamp" in data
    assert "checks" in data

    checks = data["checks"]
    assert "database" in checks
    assert checks["database"]["status"] == "ok"
    assert "ollama" in checks
    assert "voice_subsystem" in checks
    assert "policy_engine" in checks
    assert checks["policy_engine"]["details"]["default_policy"] == "DENY"
