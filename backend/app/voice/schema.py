"""Schemas and state machine for voice-first interactions."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from backend.app.core.exceptions import ValidationError


class VoiceState(StrEnum):
    """Honest states of the voice conversation loop."""

    IDLE = "IDLE"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    SPEAKING = "SPEAKING"
    INTERRUPTED = "INTERRUPTED"


class VoiceTransitionLog(BaseModel):
    """Audit record for a voice state transition."""

    from_state: VoiceState
    to_state: VoiceState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reason: str | None = None


class VoiceStateMachine:
    """Deterministic state machine governing voice turn transitions."""

    LEGAL_TRANSITIONS: dict[VoiceState, list[VoiceState]] = {
        VoiceState.IDLE: [VoiceState.LISTENING],
        VoiceState.LISTENING: [VoiceState.PROCESSING, VoiceState.IDLE],
        VoiceState.PROCESSING: [VoiceState.SPEAKING, VoiceState.IDLE],
        VoiceState.SPEAKING: [VoiceState.IDLE, VoiceState.INTERRUPTED],
        VoiceState.INTERRUPTED: [VoiceState.LISTENING, VoiceState.IDLE],
    }

    def __init__(self, initial_state: VoiceState = VoiceState.IDLE) -> None:
        self._current_state = initial_state
        self._history: list[VoiceTransitionLog] = []

    @property
    def current_state(self) -> VoiceState:
        """Return the active state."""
        return self._current_state

    @property
    def history(self) -> list[VoiceTransitionLog]:
        """Return read-only transition history."""
        return list(self._history)

    def transition_to(self, new_state: VoiceState, reason: str | None = None) -> VoiceState:
        """Attempt to transition to a new state.

        Raises ValidationError if the transition is illegal according to state rules.
        """
        # Reset to IDLE is always permitted from any state as an emergency escape / reset
        if new_state == VoiceState.IDLE and self._current_state != VoiceState.IDLE:
            allowed = True
        else:
            allowed = new_state in self.LEGAL_TRANSITIONS.get(self._current_state, [])

        if not allowed:
            raise ValidationError(
                message=f"Illegal voice state transition: cannot transition from {self._current_state.value} to {new_state.value}",
                details={
                    "from": self._current_state.value,
                    "to": new_state.value,
                    "reason": reason,
                },
            )

        log = VoiceTransitionLog(from_state=self._current_state, to_state=new_state, reason=reason)
        self._history.append(log)
        self._current_state = new_state
        return self._current_state
