"""Policy-driven proactive intervention engine evaluating confidence, usefulness, urgency, and modes."""

import time
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from backend.app.personality.schema import PersonalityMode


class InterventionOutcome(StrEnum):
    """Possible outcomes of the policy-driven intervention evaluation."""

    TALK = "TALK"
    ASK = "ASK"
    WAIT = "WAIT"
    SUPPRESS = "SUPPRESS"
    PROPOSE_ACTION = "PROPOSE_ACTION"
    PRIVACY = "PRIVACY"


class ObservationItem(BaseModel):
    """A sensory or system observation proposed for proactive intervention."""

    source: str = Field(description="Explicitly approved observation source (e.g. system_monitor, build_watcher)")
    summary: str = Field(description="Human-readable description of observed state")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in the observation accuracy")
    expected_usefulness: float = Field(ge=0.0, le=1.0, description="Estimated value to the user")
    urgency: str = Field(default="MEDIUM", description="Urgency rating: LOW, MEDIUM, HIGH, CRITICAL")
    proposed_action: dict[str, Any] | None = Field(default=None, description="Optional proposed tool call")
    timestamp: float = Field(default_factory=time.time)


class InterventionDecision(BaseModel):
    """The deterministic policy decision regarding how to handle an observation."""

    outcome: InterventionOutcome
    reason: str
    observation: ObservationItem | None = None
    proposed_action: dict[str, Any] | None = None
    auto_executed: bool = Field(default=False, description="Always False; observing does not authorize acting")


class ProactiveEngine:
    """Evaluates proposed interventions against confidence thresholds, user modes, and cooldowns."""

    def __init__(self, cooldown_seconds: int = 300) -> None:
        self.cooldown_seconds = cooldown_seconds
        self._recent_observations: dict[str, float] = {}

    def evaluate_intervention(
        self,
        observation: ObservationItem,
        current_mode: PersonalityMode,
        privacy_mode: bool = False,
        user_dnd: bool = False,
    ) -> InterventionDecision:
        """Evaluate whether to TALK, ASK, WAIT, SUPPRESS, PROPOSE_ACTION, or yield to PRIVACY."""
        # 1. Privacy Mode: strictly drop background observations
        if privacy_mode:
            return InterventionDecision(
                outcome=InterventionOutcome.PRIVACY,
                reason="Privacy Mode active: background observation and intervention suspended",
                observation=observation,
            )

        # 2. Confidence threshold check (Minimum 0.60 required)
        if observation.confidence < 0.60:
            return InterventionDecision(
                outcome=InterventionOutcome.SUPPRESS,
                reason=f"Observation confidence too low ({observation.confidence:.2f} < 0.60)",
                observation=observation,
            )

        # 3. Expected usefulness check (Minimum 0.50 required)
        if observation.expected_usefulness < 0.50:
            return InterventionDecision(
                outcome=InterventionOutcome.SUPPRESS,
                reason=f"Expected usefulness below threshold ({observation.expected_usefulness:.2f} < 0.50)",
                observation=observation,
            )

        # 4. Duplicate suppression and cooldown tracking
        key = f"{observation.source}:{observation.summary.strip().lower()}"
        now = time.time()
        last_seen = self._recent_observations.get(key)
        if last_seen is not None and (now - last_seen) < self.cooldown_seconds:
            return InterventionDecision(
                outcome=InterventionOutcome.SUPPRESS,
                reason=f"Duplicate observation suppressed by cooldown window ({int(now - last_seen)}s < {self.cooldown_seconds}s)",
                observation=observation,
            )
        self._recent_observations[key] = now

        # 5. User Do Not Disturb
        if user_dnd:
            return InterventionDecision(
                outcome=InterventionOutcome.WAIT,
                reason="User requested Do Not Disturb; alert deferred",
                observation=observation,
            )

        # 6. Mode-specific dampening
        # Quiet Mode: Never TALK verbally
        if current_mode == PersonalityMode.QUIET:
            if observation.proposed_action:
                return InterventionDecision(
                    outcome=InterventionOutcome.PROPOSE_ACTION,
                    reason="Quiet mode: proposing action silently without verbal interruption",
                    observation=observation,
                    proposed_action=observation.proposed_action,
                    auto_executed=False,
                )
            if observation.urgency.upper() == "CRITICAL":
                return InterventionDecision(
                    outcome=InterventionOutcome.ASK,
                    reason="Quiet mode: silent visual notification for critical alert",
                    observation=observation,
                )
            return InterventionDecision(
                outcome=InterventionOutcome.WAIT,
                reason="Quiet mode: non-critical verbal alerts suppressed",
                observation=observation,
            )

        # Focus Mode: Suppress/defer non-critical interruptions
        if current_mode == PersonalityMode.FOCUS:
            if observation.urgency.upper() != "CRITICAL":
                return InterventionDecision(
                    outcome=InterventionOutcome.WAIT,
                    reason="Focus mode active: non-critical alerts deferred to minimize interruption",
                    observation=observation,
                )

        # 7. Proposed Action: Always require authorization, never auto-execute
        if observation.proposed_action:
            return InterventionDecision(
                outcome=InterventionOutcome.PROPOSE_ACTION,
                reason="Action proposed for user confirmation; observing does not authorize acting",
                observation=observation,
                proposed_action=observation.proposed_action,
                auto_executed=False,
            )

        # 8. Urgency routing
        if observation.urgency.upper() in ("CRITICAL", "HIGH"):
            return InterventionDecision(
                outcome=InterventionOutcome.TALK,
                reason=f"High urgency ({observation.urgency.upper()}) routed to spoken alert",
                observation=observation,
            )

        return InterventionDecision(
            outcome=InterventionOutcome.ASK,
            reason="Moderate alert routed to gentle confirmation prompt",
            observation=observation,
        )


proactive_engine = ProactiveEngine()
