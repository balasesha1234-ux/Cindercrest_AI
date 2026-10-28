"""Safety policy engine enforcing default-DENY governance."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class PolicyDecision(StrEnum):
    """Authoritative decision from the policy engine."""

    DENY = "DENY"
    ALLOW = "ALLOW"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


class PolicyEvaluationResult(BaseModel):
    """Evaluation result for an proposed action."""

    decision: PolicyDecision
    reason: str
    metadata: dict[str, Any] | None = None


class PolicyEngine:
    """Deterministic security gatekeeper. Default policy is strictly DENY."""

    def __init__(self, privacy_mode: bool = False) -> None:
        self.privacy_mode = privacy_mode

    def evaluate_action(
        self, action_name: str, parameters: dict[str, Any] | None = None
    ) -> PolicyEvaluationResult:
        """Evaluate an action proposal.

        In Phase 0 & Phase 1 (Voice MVP), all external actions and tool side-effects
        are completely disabled by design.
        """
        if self.privacy_mode:
            return PolicyEvaluationResult(
                decision=PolicyDecision.DENY,
                reason="Privacy mode is active. Observation and external actions are disabled.",
            )

        # In voice-first foundation, all tools and computer-control actions are denied
        return PolicyEvaluationResult(
            decision=PolicyDecision.DENY,
            reason=f"Action '{action_name}' is denied: Tool execution is disabled in voice-first MVP.",
            metadata={"action": action_name, "parameters": parameters or {}},
        )
