"""Unit tests for the policy-driven proactive intervention engine."""

from backend.app.personality.schema import PersonalityMode
from backend.app.proactive.engine import InterventionOutcome, ObservationItem, ProactiveEngine


def test_privacy_mode_blocks_proactive_observations() -> None:
    """Verify that Privacy Mode strictly drops observation evaluation with PRIVACY outcome."""
    engine = ProactiveEngine()
    obs = ObservationItem(
        source="system_monitor",
        summary="Battery level is at 10%",
        confidence=0.95,
        expected_usefulness=0.9,
        urgency="HIGH",
    )

    decision = engine.evaluate_intervention(
        observation=obs,
        current_mode=PersonalityMode.WORK,
        privacy_mode=True,
    )
    assert decision.outcome == InterventionOutcome.PRIVACY
    assert decision.reason == "Privacy Mode active: background observation and intervention suspended"


def test_low_confidence_suppression() -> None:
    """Verify that observations below confidence threshold are suppressed."""
    engine = ProactiveEngine()
    obs = ObservationItem(
        source="file_watcher",
        summary="User might be looking for a draft document",
        confidence=0.45,  # Low confidence (< 0.6)
        expected_usefulness=0.8,
        urgency="LOW",
    )

    decision = engine.evaluate_intervention(
        observation=obs,
        current_mode=PersonalityMode.ADAPTIVE,
        privacy_mode=False,
    )
    assert decision.outcome == InterventionOutcome.SUPPRESS
    assert "confidence" in decision.reason.lower()


def test_low_usefulness_suppression() -> None:
    """Verify that observations with low expected usefulness are suppressed."""
    engine = ProactiveEngine()
    obs = ObservationItem(
        source="calendar_check",
        summary="Minor background reminder",
        confidence=0.9,
        expected_usefulness=0.3,  # Low usefulness (< 0.5)
        urgency="LOW",
    )

    decision = engine.evaluate_intervention(
        observation=obs,
        current_mode=PersonalityMode.WORK,
        privacy_mode=False,
    )
    assert decision.outcome == InterventionOutcome.SUPPRESS
    assert "usefulness" in decision.reason.lower()


def test_focus_mode_suppresses_non_critical_interruptions() -> None:
    """Verify that Focus mode blocks medium/low urgency interruptions, deferring to WAIT or SUPPRESS."""
    engine = ProactiveEngine()

    # Medium urgency notification -> deferred in Focus mode
    medium_obs = ObservationItem(
        source="git_status",
        summary="3 uncommitted changes detected in repository",
        confidence=0.95,
        expected_usefulness=0.85,
        urgency="MEDIUM",
    )
    decision_med = engine.evaluate_intervention(
        observation=medium_obs,
        current_mode=PersonalityMode.FOCUS,
        privacy_mode=False,
    )
    assert decision_med.outcome in (InterventionOutcome.WAIT, InterventionOutcome.SUPPRESS)

    # Critical urgency notification -> allowed in Focus mode
    critical_obs = ObservationItem(
        source="hardware_sensor",
        summary="CPU temperature exceeded 98C critical threshold",
        confidence=0.98,
        expected_usefulness=0.95,
        urgency="CRITICAL",
    )
    decision_crit = engine.evaluate_intervention(
        observation=critical_obs,
        current_mode=PersonalityMode.FOCUS,
        privacy_mode=False,
    )
    assert decision_crit.outcome in (InterventionOutcome.TALK, InterventionOutcome.ASK)


def test_quiet_mode_prevents_verbal_talk() -> None:
    """Verify that Quiet mode forbids TALK outcomes, converting them to WAIT or silent proposals."""
    engine = ProactiveEngine()
    obs = ObservationItem(
        source="battery_check",
        summary="Battery at 15%",
        confidence=0.95,
        expected_usefulness=0.9,
        urgency="HIGH",
    )

    decision = engine.evaluate_intervention(
        observation=obs,
        current_mode=PersonalityMode.QUIET,
        privacy_mode=False,
    )
    # Never TALK out loud in Quiet mode
    assert decision.outcome != InterventionOutcome.TALK
    assert decision.outcome in (InterventionOutcome.WAIT, InterventionOutcome.ASK, InterventionOutcome.SUPPRESS)


def test_duplicate_suppression_and_cooldown() -> None:
    """Verify that repeated observations for the same issue are suppressed during cooldown window."""
    engine = ProactiveEngine(cooldown_seconds=60)
    obs = ObservationItem(
        source="disk_space",
        summary="Drive C: free space below 2 GB",
        confidence=0.95,
        expected_usefulness=0.9,
        urgency="HIGH",
    )

    # First observation evaluates successfully
    first_decision = engine.evaluate_intervention(
        observation=obs,
        current_mode=PersonalityMode.WORK,
        privacy_mode=False,
    )
    assert first_decision.outcome in (InterventionOutcome.TALK, InterventionOutcome.ASK)

    # Immediate second observation of identical issue is suppressed
    second_decision = engine.evaluate_intervention(
        observation=obs,
        current_mode=PersonalityMode.WORK,
        privacy_mode=False,
    )
    assert second_decision.outcome == InterventionOutcome.SUPPRESS
    assert "cooldown" in second_decision.reason.lower() or "duplicate" in second_decision.reason.lower()


def test_proposing_action_never_auto_executes() -> None:
    """Law: 'Observing something does not authorize acting on it'. Propose action returns proposal only."""
    engine = ProactiveEngine()
    obs = ObservationItem(
        source="build_watcher",
        summary="Build failed with 1 syntax error in file backend/app/main.py",
        confidence=0.95,
        expected_usefulness=0.88,
        urgency="MEDIUM",
        proposed_action={"tool": "fs.read_text", "parameters": {"path": "backend/app/main.py"}},
    )

    decision = engine.evaluate_intervention(
        observation=obs,
        current_mode=PersonalityMode.WORK,
        privacy_mode=False,
    )
    assert decision.outcome == InterventionOutcome.PROPOSE_ACTION
    assert decision.proposed_action is not None
    assert decision.proposed_action.get("tool") == "fs.read_text"
    # Auto-execution flag MUST be False
    assert decision.auto_executed is False
