"""Conversational API endpoints supporting text and spoken interaction."""

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.app.core.security import verify_session_token
from backend.app.model.router import ModelRouter, get_model_router
from backend.app.orchestrator.conversation import (
    ConversationSession,
    ConversationTurn,
    get_conversation_session,
)

router = APIRouter(prefix="/api/v1/conversation", tags=["Conversation"])


class ChatRequest(BaseModel):
    """Chat request payload for spoken transcript or text fallback."""

    text: str = Field(min_length=1, description="User utterance or typed input text")
    provider: str | None = Field(
        default=None, description="Optional provider override ('ollama', 'groq')"
    )
    stream: bool = Field(default=False, description="Whether to stream response tokens")
    privacy_mode: bool = Field(default=False, description="Whether Privacy Mode is active")


class ChatResponse(BaseModel):
    """Non-streaming conversational reply."""

    reply: str
    turn_index: int
    latency_ms: float | None
    model_used: str


@router.post("/chat", response_model=ChatResponse)
async def post_chat(
    req: ChatRequest,
    token: str = Depends(verify_session_token),
    session: ConversationSession = Depends(get_conversation_session),
    router: ModelRouter = Depends(get_model_router),
) -> Any:
    """Submit a conversational turn from voice transcript or text fallback."""
    if req.stream:

        async def event_generator() -> AsyncIterator[str]:
            try:
                async for token_text in session.stream_turn(
                    req.text,
                    router=router,
                    provider_id=req.provider,
                    privacy_mode=req.privacy_mode,
                ):
                    data = json.dumps({"delta": token_text})
                    yield f"data: {data}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as exc:
                err_data = json.dumps({"error": str(exc)})
                yield f"data: {err_data}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    assistant_turn = await session.execute_turn(
        req.text,
        router=router,
        provider_id=req.provider,
        privacy_mode=req.privacy_mode,
    )
    provider = router.get_provider(req.provider)
    return ChatResponse(
        reply=assistant_turn.content,
        turn_index=assistant_turn.turn_index,
        latency_ms=assistant_turn.latency_ms,
        model_used=provider.model_name,
    )


@router.get("/history", response_model=list[ConversationTurn])
async def get_history(
    token: str = Depends(verify_session_token),
    session: ConversationSession = Depends(get_conversation_session),
) -> list[ConversationTurn]:
    """Retrieve full conversation turn history for the active session."""
    return session.turns


@router.post("/reset")
async def post_reset(
    token: str = Depends(verify_session_token),
    session: ConversationSession = Depends(get_conversation_session),
) -> dict[str, Any]:
    """Reset the conversational context and history for a fresh start."""
    turn_count = len(session.turns)
    session.clear()
    return {"status": "reset", "turns_cleared": turn_count}


@router.get("/models")
async def get_models(
    token: str = Depends(verify_session_token),
    router: ModelRouter = Depends(get_model_router),
) -> list[dict[str, Any]]:
    """List available conversational models and their live availability."""
    return await router.list_providers_status()
