"""Unit tests for the voice state machine."""

import pytest

from backend.app.core.exceptions import ValidationError
from backend.app.voice.schema import VoiceState, VoiceStateMachine


def test_state_machine_initial_state() -> None:
    """Verify that the state machine begins in IDLE."""
    sm = VoiceStateMachine()
    assert sm.current_state == VoiceState.IDLE
    assert len(sm.history) == 0


def test_legal_conversation_cycle() -> None:
    """Verify standard conversation flow: IDLE -> LISTENING -> PROCESSING -> SPEAKING -> IDLE."""
    sm = VoiceStateMachine()

    assert sm.transition_to(VoiceState.LISTENING) == VoiceState.LISTENING
    assert sm.transition_to(VoiceState.PROCESSING) == VoiceState.PROCESSING
    assert sm.transition_to(VoiceState.SPEAKING) == VoiceState.SPEAKING
    assert sm.transition_to(VoiceState.IDLE) == VoiceState.IDLE

    assert len(sm.history) == 4


def test_barge_in_cycle() -> None:
    """Verify barge-in flow: SPEAKING -> INTERRUPTED -> LISTENING."""
    sm = VoiceStateMachine(initial_state=VoiceState.SPEAKING)

    assert (
        sm.transition_to(VoiceState.INTERRUPTED, reason="User began speaking")
        == VoiceState.INTERRUPTED
    )
    assert sm.transition_to(VoiceState.LISTENING) == VoiceState.LISTENING
    assert len(sm.history) == 2


def test_illegal_transition_raises_validation_error() -> None:
    """Verify that illegal jumps (e.g. IDLE directly to SPEAKING) are rejected."""
    sm = VoiceStateMachine(initial_state=VoiceState.IDLE)

    with pytest.raises(ValidationError) as exc:
        sm.transition_to(VoiceState.SPEAKING)

    assert "Illegal voice state transition" in str(exc.value)
    assert sm.current_state == VoiceState.IDLE
