"""Integration tests for personality modes and proactive assistance API."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import get_settings
from backend.app.main import app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers() -> dict[str, str]:
    settings = get_settings()
    return {"Authorization": f"Bearer {settings.SESSION_TOKEN}"}


def test_personality_mode_api_lifecycle(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Verify getting and setting personality modes via REST API."""
    # 1. Get current mode
    get_res = client.get("/api/v1/personality/mode", headers=auth_headers)
    assert get_res.status_code == 200
    data = get_res.json()
    assert "active_mode" in data
    assert "available_modes" in data

    # 2. Switch mode to 'focus'
    post_res = client.post(
        "/api/v1/personality/mode",
        headers=auth_headers,
        json={"mode": "focus"},
    )
    assert post_res.status_code == 200
    post_data = post_res.json()
    assert post_data["active_mode"] == "focus"
    assert post_data["config"]["verbosity"] == "low"

    # 3. Switch mode to 'relax'
    relax_res = client.post(
        "/api/v1/personality/mode",
        headers=auth_headers,
        json={"mode": "relax"},
    )
    assert relax_res.status_code == 200
    assert relax_res.json()["active_mode"] == "relax"


def test_proactive_evaluate_api(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Verify evaluating an observation through proactive intervention API."""
    obs_payload = {
        "observation": {
            "source": "api_test_sensor",
            "summary": "Urgent security patch required for runtime component",
            "confidence": 0.99,
            "expected_usefulness": 0.95,
            "urgency": "CRITICAL",
        },
        "privacy_mode": False,
    }

    res = client.post(
        "/api/v1/proactive/evaluate",
        headers=auth_headers,
        json=obs_payload,
    )
    assert res.status_code == 200
    decision = res.json()
    assert decision["outcome"] in ("TALK", "ASK")
    assert "outcome" in decision
    assert "reason" in decision


def test_unauthorized_personality_requests_rejected(client: TestClient) -> None:
    """Verify that requests without session token return 401 Unauthorized."""
    res = client.get("/api/v1/personality/mode")
    assert res.status_code == 401
