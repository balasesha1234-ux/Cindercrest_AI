"""Unit tests for model router and provider management."""

from collections.abc import AsyncIterator

import pytest

from backend.app.core.exceptions import AppError
from backend.app.model.base import ChatMessage, LLMProvider
from backend.app.model.router import ModelRouter


class LabeledMockTestProvider(LLMProvider):
    """Explicitly labeled test mock provider for unit testing (AGENTS.md Rule 1)."""

    def __init__(self, provider_id: str = "mock-test", model_name: str = "test-model") -> None:
        self._provider_id = provider_id
        self._model_name = model_name

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def model_name(self) -> str:
        return self._model_name

    async def is_available(self) -> bool:
        return True

    async def stream_chat(
        self, messages: list[ChatMessage], system_prompt: str
    ) -> AsyncIterator[str]:
        yield "Hello "
        yield "world!"

    async def generate_chat(self, messages: list[ChatMessage], system_prompt: str) -> str:
        return "Hello world!"


def test_model_router_registration_and_lookup() -> None:
    """Verify provider registration and retrieval."""
    router = ModelRouter()
    mock_prov = LabeledMockTestProvider(provider_id="custom-mock")
    router.register_provider(mock_prov)

    resolved = router.get_provider("custom-mock")
    assert resolved.provider_id == "custom-mock"
    assert resolved.model_name == "test-model"


def test_model_router_unknown_provider_raises_error() -> None:
    """Verify that requesting an unregistered provider raises NOT_FOUND."""
    router = ModelRouter()
    with pytest.raises(AppError) as exc:
        router.get_provider("non-existent-provider")

    assert exc.value.code == "NOT_FOUND"
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_list_providers_status() -> None:
    """Verify that listing providers returns availability and default flags."""
    router = ModelRouter()
    mock_prov = LabeledMockTestProvider(provider_id="active-mock")
    router.register_provider(mock_prov)

    statuses = await router.list_providers_status()
    assert len(statuses) >= 2
    mock_entry = next((s for s in statuses if s["provider_id"] == "active-mock"), None)
    assert mock_entry is not None
    assert mock_entry["is_available"] is True


@pytest.mark.asyncio
async def test_groq_provider_availability() -> None:
    """Verify GroqProvider availability based on API key configuration."""
    from backend.app.model.groq import GroqProvider

    unconfigured = GroqProvider(api_key=None)
    assert await unconfigured.is_available() is False

    configured = GroqProvider(api_key="gsk_testdummykey1234567890abcdef")
    assert await configured.is_available() is True
    assert configured.provider_id == "groq"
    assert configured.model_name == "qwen/qwen3.8-27b"
