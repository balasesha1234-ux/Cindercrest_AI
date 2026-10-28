"""Unit tests for the AgentPolicyEngine enforcing default-DENY governance."""

from typing import Any

from backend.app.agent.policy import AgentPolicyEngine
from backend.app.agent.schema import PolicyDecision, ToolSafetyTier
from backend.app.agent.tools.registry import ToolDefinition, ToolRegistry


def test_policy_denies_unknown_tools() -> None:
    policy = AgentPolicyEngine()
    result = policy.evaluate_action("unknown_tool_xyz", {})
    assert result.decision == PolicyDecision.DENY
    assert "not registered" in result.reason.lower() or "does not exist" in result.reason.lower()


def test_policy_denies_in_privacy_mode() -> None:
    policy = AgentPolicyEngine()
    result = policy.evaluate_action("datetime_now", {}, privacy_mode=True)
    assert result.decision == PolicyDecision.DENY
    assert "privacy mode" in result.reason.lower()


def test_policy_denies_destructive_tools() -> None:
    custom_registry = ToolRegistry()

    async def dummy_handler(p: dict[str, Any]) -> dict[str, Any]:
        return {}

    custom_registry.register(
        ToolDefinition(
            name="format_disk",
            description="Destructive action",
            safety_tier=ToolSafetyTier.DESTRUCTIVE,
            parameters_schema={},
            handler=dummy_handler,
        )
    )
    policy = AgentPolicyEngine(registry=custom_registry)
    result = policy.evaluate_action("format_disk", {})
    assert result.decision == PolicyDecision.DENY
    assert "destructive" in result.reason.lower()


def test_policy_blocks_shell_injection_patterns() -> None:
    policy = AgentPolicyEngine()
    malicious_inputs = [
        {"expression": "1 + 1; rm -rf /"},
        {"expression": "2 + 2 && format c:"},
        {"expression": "powershell -c evil()"},
        {"expression": "test `whoami`"},
        {"expression": "calc $(whoami)"},
    ]
    for params in malicious_inputs:
        result = policy.evaluate_action("calculator", params)
        assert result.decision == PolicyDecision.DENY
        assert "injection" in result.reason.lower() or "forbidden" in result.reason.lower()


def test_policy_allows_safe_registered_read_tools() -> None:
    policy = AgentPolicyEngine()
    # datetime_now
    res1 = policy.evaluate_action("datetime_now", {})
    assert res1.decision == PolicyDecision.ALLOW

    # calculator with valid expression
    res2 = policy.evaluate_action("calculator", {"expression": "100 / 4 + 25"})
    assert res2.decision == PolicyDecision.ALLOW

    # system_diagnostics
    res3 = policy.evaluate_action("system_diagnostics", {})
    assert res3.decision == PolicyDecision.ALLOW

    # text_analyzer
    res4 = policy.evaluate_action("text_analyzer", {"text": "hello world"})
    assert res4.decision == PolicyDecision.ALLOW
