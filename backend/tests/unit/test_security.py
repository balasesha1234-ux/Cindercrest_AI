"""Unit tests for token authentication and security boundaries."""

from fastapi.testclient import TestClient

from backend.tests.conftest import TEST_TOKEN


def test_protected_route_without_token_returns_401(client: TestClient) -> None:
    """Verify that requests missing the Authorization header return 401 with standard error schema."""
    resp = client.get("/api/v1/auth/verify")
    assert resp.status_code == 401
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "UNAUTHORIZED"
    assert "Authorization header" in data["error"]["message"]


def test_protected_route_with_invalid_token_returns_401(client: TestClient) -> None:
    """Verify that requests with an incorrect token return 401."""
    resp = client.get(
        "/api/v1/auth/verify",
        headers={"Authorization": "Bearer invalid-wrong-token-abc"},
    )
    assert resp.status_code == 401
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "UNAUTHORIZED"
    assert "Invalid or expired" in data["error"]["message"]


def test_protected_route_with_valid_token_succeeds(client: TestClient) -> None:
    """Verify that requests with the valid session token succeed."""
    resp = client.get(
        "/api/v1/auth/verify",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["authenticated"] is True
    assert data["session_active"] is True
    assert data["token_prefix"].startswith(TEST_TOKEN[:6])
