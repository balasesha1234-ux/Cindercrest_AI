"""Integration tests for the conversation and voice API endpoints."""

from fastapi.testclient import TestClient

from backend.app.model.router import get_model_router
from backend.tests.conftest import TEST_TOKEN
from backend.tests.unit.test_model_router import LabeledMockTestProvider


def test_conversation_chat_endpoint_success(client: TestClient) -> None:
    """Verify that submitting a chat turn returns an intelligent reply and records history."""
    router = get_model_router()
    router.register_provider(LabeledMockTestProvider(provider_id="mock-api"))

    resp = client.post(
        "/api/v1/conversation/chat",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
        json={"text": "Hello Cindercrest, how are you?", "provider": "mock-api"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["reply"] == "Hello world!"
    assert data["turn_index"] >= 2
    assert data["model_used"] == "test-model"
    assert data["latency_ms"] is not None


def test_conversation_history_endpoint(client: TestClient) -> None:
    """Verify that history returns turn logs."""
    resp = client.get(
        "/api/v1/conversation/history",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    assert resp.status_code == 200
    history = resp.json()
    assert isinstance(history, list)
    assert len(history) >= 2


def test_conversation_reset_endpoint(client: TestClient) -> None:
    """Verify that reset clears active turns."""
    resp = client.post(
        "/api/v1/conversation/reset",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "reset"

    # History should now be empty
    hist_resp = client.get(
        "/api/v1/conversation/history",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    assert len(hist_resp.json()) == 0


def test_synthesizer_info_endpoint(client: TestClient) -> None:
    """Verify speech synthesizer discovery endpoint."""
    resp = client.get(
        "/api/v1/voice/synthesizer",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "engine" in data
    assert "supported_voices" in data
    assert len(data["supported_voices"]) >= 1


def test_unauthorized_conversation_rejected(client: TestClient) -> None:
    """Verify that conversation routes require authentication."""
    resp = client.post(
        "/api/v1/conversation/chat",
        json={"text": "Unauthorized request"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_transcribe_with_client_transcript(client: TestClient) -> None:
    """Verify transcription endpoint accepts client speech transcripts."""
    resp = client.post(
        "/api/v1/voice/transcribe",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
        json={"client_transcript": "Hello computer", "confidence": 0.95},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["transcript"] == "Hello computer"
    assert data["confidence"] == 0.95
    assert data["engine"] == "client-speech-recognition"


def test_transcribe_audio_base64_not_implemented_returns_501(client: TestClient) -> None:
    """Verify server-side transcription honestly returns NOT_IMPLEMENTED before V1-B (AGENTS.md Rule 1)."""
    resp = client.post(
        "/api/v1/voice/transcribe",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
        json={"audio_base64": "UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA="},
    )
    assert resp.status_code == 501
    assert resp.json()["error"]["code"] == "NOT_IMPLEMENTED"


def test_transcribe_empty_payload_rejected(client: TestClient) -> None:
    """Verify transcribe rejects empty payload."""
    resp = client.post(
        "/api/v1/voice/transcribe",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
        json={},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
