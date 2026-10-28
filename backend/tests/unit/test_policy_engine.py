"""Unit tests for default-DENY policy engine."""

from backend.app.policy.engine import PolicyDecision, PolicyEngine


def test_default_policy_denies_all_actions() -> None:
    """Verify that any proposed action is denied by default in the voice-first foundation."""
    engine = PolicyEngine(privacy_mode=False)

    res1 = engine.evaluate_action("launch_application", {"app": "notepad"})
    assert res1.decision == PolicyDecision.DENY
    assert "Tool execution is disabled" in res1.reason

    res2 = engine.evaluate_action("read_file", {"path": "C:/test.txt"})
    assert res2.decision == PolicyDecision.DENY


def test_privacy_mode_denies_all_actions() -> None:
    """Verify that privacy mode explicitly overrides and denies all actions."""
    engine = PolicyEngine(privacy_mode=True)

    res = engine.evaluate_action("listen_microphone")
    assert res.decision == PolicyDecision.DENY
    assert "Privacy mode is active" in res.reason
