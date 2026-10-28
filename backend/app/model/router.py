"""Model router resolving active conversational provider."""

from typing import Any

from backend.app.core.config import Settings, get_settings
from backend.app.core.exceptions import AppError
from backend.app.model.base import LLMProvider
from backend.app.model.groq import GroqProvider
from backend.app.model.ollama import OllamaProvider


class ModelRouter:
    """Manages active LLM provider adapters and model resolution."""

    def __init__(self, settings: Settings | None = None) -> None:
        cfg = settings or get_settings()
        self._providers: dict[str, LLMProvider] = {
            "ollama": OllamaProvider(base_url=cfg.OLLAMA_BASE_URL, model_name=cfg.OLLAMA_MODEL),
            "groq": GroqProvider(api_key=cfg.GROQ_API_KEY, model_name=cfg.GROQ_MODEL),
        }
        self._default_provider_id = "groq" if cfg.GROQ_API_KEY else "ollama"

    def register_provider(self, provider: LLMProvider) -> None:
        """Register or override a provider adapter."""
        self._providers[provider.provider_id] = provider

    def get_provider(self, requested_id: str | None = None) -> LLMProvider:
        """Resolve the appropriate provider adapter."""
        if requested_id:
            key = requested_id.lower().strip()
            if key not in self._providers:
                raise AppError(
                    message=f"Model provider '{requested_id}' is not registered. Available: {list(self._providers.keys())}",
                    code="NOT_FOUND",
                    status_code=404,
                )
            return self._providers[key]

        return self._providers[self._default_provider_id]

    async def list_providers_status(self) -> list[dict[str, Any]]:
        """List registered providers with active health and model details."""
        statuses = []
        for pid, provider in self._providers.items():
            is_avail = await provider.is_available()
            statuses.append(
                {
                    "provider_id": pid,
                    "model_name": provider.model_name,
                    "is_available": is_avail,
                    "is_default": pid == self._default_provider_id,
                }
            )
        return statuses


# Global router singleton
_router = ModelRouter()


def get_model_router() -> ModelRouter:
    """Dependency provider for ModelRouter."""
    return _router
