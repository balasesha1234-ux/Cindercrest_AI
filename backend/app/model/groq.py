"""Groq hosted model provider adapter for high-speed conversational inference."""

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from backend.app.core.exceptions import AppError
from backend.app.core.logging import logger
from backend.app.model.base import ChatMessage, LLMProvider


class GroqProvider(LLMProvider):
    """Adapter for hosted Groq Cloud OpenAI-compatible API."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "qwen/qwen3.8-27b",
    ) -> None:
        self._api_key = api_key
        self._model_name = model_name
        self._endpoint = "https://api.groq.com/openai/v1/chat/completions"

    @property
    def provider_id(self) -> str:
        return "groq"

    @property
    def model_name(self) -> str:
        return self._model_name

    async def is_available(self) -> bool:
        """Check if a Groq API key is configured."""
        return bool(self._api_key and self._api_key.strip())

    def _format_messages(
        self, messages: list[ChatMessage], system_prompt: str
    ) -> list[dict[str, str]]:
        formatted = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            formatted.append({"role": msg.role, "content": msg.content})
        return formatted

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        system_prompt: str,
    ) -> AsyncIterator[str]:
        """Stream conversational tokens from Groq API."""
        if not self._api_key:
            raise AppError(
                message="Groq API key not configured. Set GROQ_API_KEY in environment variables.",
                code="AUTH_REQUIRED",
                status_code=400,
            )

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self._model_name,
            "messages": self._format_messages(messages, system_prompt),
            "temperature": 0.7,
            "max_tokens": 600,
            "stream": True,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream(
                    "POST", self._endpoint, headers=headers, json=payload
                ) as response:
                    if response.status_code != 200:
                        error_body = await response.aread()
                        raise AppError(
                            message=f"Groq API error (HTTP {response.status_code}): {error_body.decode('utf-8', errors='replace')}",
                            code="GROQ_ERROR",
                            status_code=502,
                        )

                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line:
                            continue
                        if line == "data: [DONE]":
                            break
                        if line.startswith("data: "):
                            data_str = line[6:].strip()
                            try:
                                chunk = json.loads(data_str)
                                choices = chunk.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                            except Exception:
                                continue

        except httpx.RequestError as exc:
            logger.error("Groq network error: %s", exc)
            raise AppError(
                message=f"Network error connecting to Groq API: {exc}",
                code="NETWORK_ERROR",
                status_code=502,
            )

    async def generate_chat(
        self,
        messages: list[ChatMessage],
        system_prompt: str,
    ) -> str:
        """Generate a complete conversational response from Groq API."""
        if not self._api_key:
            raise AppError(
                message="Groq API key not configured. Set GROQ_API_KEY in environment variables.",
                code="AUTH_REQUIRED",
                status_code=400,
            )

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self._model_name,
            "messages": self._format_messages(messages, system_prompt),
            "temperature": 0.7,
            "max_tokens": 600,
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self._endpoint, headers=headers, json=payload)
                if response.status_code != 200:
                    raise AppError(
                        message=f"Groq API error (HTTP {response.status_code}): {response.text}",
                        code="GROQ_ERROR",
                        status_code=502,
                    )

                data = response.json()
                choices = data.get("choices", [])
                if not choices:
                    return "I did not receive a response from the model."
                return str(choices[0].get("message", {}).get("content", "")).strip()

        except httpx.RequestError as exc:
            logger.error("Groq network error: %s", exc)
            raise AppError(
                message=f"Network error connecting to Groq API: {exc}",
                code="NETWORK_ERROR",
                status_code=502,
            )
