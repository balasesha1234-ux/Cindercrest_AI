"""Abstract base classes and contracts for conversational language models."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """A single turn in a conversational exchange."""

    role: str = Field(description="Speaker role: 'user', 'assistant', or 'system'")
    content: str = Field(description="Message text")


class LLMProvider(ABC):
    """Abstract provider adapter for conversational LLM backends."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique provider identifier (e.g. 'ollama', 'groq')."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Name of the model served by this provider."""
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Check whether the provider runtime is currently reachable."""
        pass

    @abstractmethod
    def stream_chat(
        self,
        messages: list[ChatMessage],
        system_prompt: str,
    ) -> AsyncIterator[str]:
        """Stream response tokens asynchronously."""
        pass

    @abstractmethod
    async def generate_chat(
        self,
        messages: list[ChatMessage],
        system_prompt: str,
    ) -> str:
        """Generate a complete response non-streaming."""
        pass
