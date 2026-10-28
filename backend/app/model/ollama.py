"""Ollama local model provider adapter."""

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from backend.app.core.exceptions import AppError
from backend.app.core.logging import logger
from backend.app.model.base import ChatMessage, LLMProvider


class OllamaProvider(LLMProvider):
    """Adapter for locally hosted Ollama inference engine."""

    def __init__(
        self, base_url: str = "http://127.0.0.1:11434", model_name: str = "qwen3:8b"
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model_name = model_name

    @property
    def provider_id(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self._model_name

    async def is_available(self) -> bool:
        """Check if local Ollama daemon is reachable."""
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                resp = await client.get(f"{self._base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    def _format_payload(
        self, messages: list[ChatMessage], system_prompt: str, stream: bool
    ) -> dict[str, Any]:
        formatted_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            formatted_messages.append({"role": msg.role, "content": msg.content})

        return {
            "model": self._model_name,
            "messages": formatted_messages,
            "stream": stream,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
            },
        }

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        system_prompt: str,
    ) -> AsyncIterator[str]:
        """Stream conversational tokens from local Ollama service."""
        payload = self._format_payload(messages, system_prompt, stream=True)
        url = f"{self._base_url}/api/chat"

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0)) as client:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        raise AppError(
                            message=f"Ollama returned HTTP {response.status_code}: {error_text.decode('utf-8', errors='replace')}",
                            code="OLLAMA_ERROR",
                            status_code=502,
                        )

                    async for line in response.aiter_lines():
                        if not line or not line.strip():
                            continue
                        try:
                            chunk = json.loads(line)
                            content = chunk.get("message", {}).get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue

        except httpx.ConnectError:
            logger.error("Failed to connect to Ollama at %s", self._base_url)
            raise AppError(
                message=f"Cannot connect to local Ollama service at {self._base_url}. Ensure Ollama is running ('ollama serve').",
                code="OLLAMA_UNREACHABLE",
                status_code=503,
            )
        except httpx.TimeoutException:
            logger.error("Timeout waiting for Ollama response from %s", self._model_name)
            raise AppError(
                message=f"Ollama model '{self._model_name}' timed out during generation.",
                code="OLLAMA_TIMEOUT",
                status_code=504,
            )

    async def generate_chat(
        self,
        messages: list[ChatMessage],
        system_prompt: str,
    ) -> str:
        """Generate complete conversational response."""
        tokens: list[str] = []
        async for token in self.stream_chat(messages, system_prompt):
            tokens.append(token)
        return "".join(tokens)
