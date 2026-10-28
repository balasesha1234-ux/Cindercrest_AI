"""Personality mode schemas, tone configurations, and request models."""

from enum import StrEnum

from pydantic import BaseModel, Field


class PersonalityMode(StrEnum):
    """Configurable personality modes altering tone, verbosity, and initiative."""

    ADAPTIVE = "adaptive"
    WORK = "work"
    FOCUS = "focus"
    RELAX = "relax"
    COACH = "coach"
    QUIET = "quiet"
    SERIOUS = "serious"


class ModeConfig(BaseModel):
    """Configuration parameters governing assistant demeanor and communication bounds."""

    mode: PersonalityMode
    tone_description: str
    prompt_modifier: str
    verbosity: str = Field(description="'minimal', 'low', 'balanced', or 'verbose'")
    initiative: float = Field(ge=0.0, le=1.0, description="Proactivity threshold (0.0=passive, 1.0=assertive)")
    allow_playful_banter: bool = False
    interruption_threshold: str = Field(default="MEDIUM", description="Minimum urgency to interrupt: LOW, MEDIUM, HIGH, CRITICAL")


class ModeResponse(BaseModel):
    """Response payload for current mode and active config."""

    active_mode: PersonalityMode
    config: ModeConfig
    available_modes: list[str]


class ChangeModeRequest(BaseModel):
    """Request payload to change active personality mode."""

    mode: PersonalityMode
