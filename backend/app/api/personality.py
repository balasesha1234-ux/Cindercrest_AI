"""REST API endpoints for personality mode switching and proactive assistance evaluation."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.core.security import verify_session_token
from backend.app.personality.manager import personality_manager
from backend.app.personality.schema import (
    ChangeModeRequest,
    ModeResponse,
    PersonalityMode,
)
from backend.app.proactive.engine import (
    InterventionDecision,
    ObservationItem,
    proactive_engine,
)

router = APIRouter(prefix="/api/v1", tags=["Personality & Proactivity"])


class EvaluateProactiveRequest(BaseModel):
    """Payload to evaluate an observation through the proactive intervention engine."""

    observation: ObservationItem
    privacy_mode: bool = Field(default=False, description="Whether system Privacy Mode is active")
    user_dnd: bool = Field(default=False, description="Whether user requested Do Not Disturb")


@router.get(
    "/personality/mode",
    response_model=ModeResponse,
    dependencies=[Depends(verify_session_token)],
)
async def get_personality_mode() -> ModeResponse:
    """Retrieve the active personality mode and its configuration."""
    active = personality_manager.active_mode
    config = personality_manager.get_active_config()
    available = [m.value for m in PersonalityMode]
    return ModeResponse(
        active_mode=active,
        config=config,
        available_modes=available,
    )


@router.post(
    "/personality/mode",
    response_model=ModeResponse,
    dependencies=[Depends(verify_session_token)],
)
async def set_personality_mode(req: ChangeModeRequest) -> ModeResponse:
    """Change the active personality mode."""
    personality_manager.set_mode(req.mode)
    config = personality_manager.get_active_config()
    available = [m.value for m in PersonalityMode]
    return ModeResponse(
        active_mode=req.mode,
        config=config,
        available_modes=available,
    )


@router.post(
    "/proactive/evaluate",
    response_model=InterventionDecision,
    dependencies=[Depends(verify_session_token)],
)
async def evaluate_proactive_alert(req: EvaluateProactiveRequest) -> InterventionDecision:
    """Evaluate an observation through the policy-driven intervention engine."""
    current_mode = personality_manager.active_mode
    decision = proactive_engine.evaluate_intervention(
        observation=req.observation,
        current_mode=current_mode,
        privacy_mode=req.privacy_mode,
        user_dnd=req.user_dnd,
    )
    return decision
