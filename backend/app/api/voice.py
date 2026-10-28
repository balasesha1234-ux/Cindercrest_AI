"""Voice state introspection, transcription, and speech management endpoints."""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.core.config import Settings, get_settings
from backend.app.core.exceptions import AppError, ValidationError
from backend.app.core.security import verify_session_token
from backend.app.voice.schema import VoiceState, VoiceStateMachine

router = APIRouter(prefix="/api/v1/voice", tags=["Voice"])

# Module-level singleton state machine for runtime voice session
_voice_sm = VoiceStateMachine(initial_state=VoiceState.IDLE)


def get_voice_state_machine() -> VoiceStateMachine:
    """Return the active voice state machine."""
    return _voice_sm


class VoiceStateResponse(BaseModel):
    """Voice state status response."""

    current_state: VoiceState
    history_count: int


class VoiceTransitionRequest(BaseModel):
    """Request to transition to a new voice state."""

    target_state: VoiceState
    reason: str | None = None


class TranscribeRequest(BaseModel):
    """Transcription input data payload."""

    audio_base64: str | None = Field(
        default=None, description="Base64 encoded PCM or WAV audio bytes"
    )
    client_transcript: str | None = Field(
        default=None, description="Client-side verified transcript"
    )
    confidence: float | None = Field(default=1.0, description="Speech recognition confidence score")


class TranscribeResponse(BaseModel):
    """Transcription result payload."""

    transcript: str
    confidence: float
    engine: str


@router.get("/state", response_model=VoiceStateResponse)
async def get_state(
    token: str = Depends(verify_session_token),
    sm: VoiceStateMachine = Depends(get_voice_state_machine),
) -> VoiceStateResponse:
    """Get the active voice state."""
    return VoiceStateResponse(
        current_state=sm.current_state,
        history_count=len(sm.history),
    )


@router.post("/transition", response_model=VoiceStateResponse)
async def post_transition(
    req: VoiceTransitionRequest,
    token: str = Depends(verify_session_token),
    sm: VoiceStateMachine = Depends(get_voice_state_machine),
) -> VoiceStateResponse:
    """Transition the voice engine to a new state under strict state machine rules."""
    new_state = sm.transition_to(req.target_state, reason=req.reason)
    return VoiceStateResponse(
        current_state=new_state,
        history_count=len(sm.history),
    )


@router.post("/transcribe", response_model=TranscribeResponse)
async def post_transcribe(
    req: TranscribeRequest,
    token: str = Depends(verify_session_token),
) -> TranscribeResponse:
    """Process speech recognition input and return verified transcript."""
    if req.client_transcript is not None:
        text = req.client_transcript.strip()
        return TranscribeResponse(
            transcript=text,
            confidence=req.confidence or 1.0,
            engine="client-speech-recognition",
        )
    if req.audio_base64:
        raise AppError(
            message="Server-side Faster-Whisper daemon transcription is scheduled for Milestone V1-B. Client speech recognition is active in V1-A.",
            code="NOT_IMPLEMENTED",
            status_code=501,
        )
    raise ValidationError(message="Either client_transcript or audio_base64 must be provided")


@router.get("/synthesizer")
async def get_synthesizer_info(
    token: str = Depends(verify_session_token),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Return local speech synthesis capabilities."""
    return {
        "engine": settings.VOICE_DEFAULT_SYNTHESIZER,
        "sample_rate": settings.VOICE_SAMPLE_RATE,
        "supported_voices": [
            {
                "id": "onecore-heera",
                "name": "Microsoft Heera (Natural English)",
                "gender": "female",
            },
            {"id": "onecore-zira", "name": "Microsoft Zira (English US)", "gender": "female"},
            {"id": "onecore-david", "name": "Microsoft David (English US)", "gender": "male"},
        ],
    }
