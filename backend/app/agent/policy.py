"""Deterministic policy evaluation engine enforcing default-DENY security governance."""

import re
from typing import Any

import backend.app.agent.tools.builtins  # noqa: F401 - ensure builtins are registered
import backend.app.agent.tools.filesystem  # noqa: F401 - ensure fs tools are registered
from backend.app.agent.schema import PolicyDecision, PolicyEvaluationResult, ToolSafetyTier
from backend.app.agent.tools.filesystem import FilesystemGuard
from backend.app.agent.tools.filesystem import fs_guard as default_fs_guard
from backend.app.agent.tools.registry import ToolRegistry, tool_registry

# Patterns associated with shell injection and command execution
SHELL_INJECTION_PATTERNS = [
    r";\s*\w+",  # command chaining ;
    r"&&\s*\w+",  # command chaining &&
    r"\|\|\s*\w+",  # command chaining ||
    r"`[^`]+`",  # backtick evaluation
    r"\$\([^\)]+\)",  # subshell $(...)
    r"\${[^}]+}",  # shell variable expansion ${...}
    r"\b(rm\s+-rf|format\s+[a-z]:|powershell|cmd\.exe|bash|sh|curl|wget)\b",
]


class AgentPolicyEngine:
    """Security gatekeeper evaluating proposed tool invocations against policy rules.

    Default policy is strictly DENY.
    """

    def __init__(
        self,
        registry: ToolRegistry | None = None,
        fs_guard: FilesystemGuard | None = None,
    ) -> None:
        self.registry = registry or tool_registry
        self.fs_guard = fs_guard or default_fs_guard

    def evaluate_action(
        self,
        tool_name: str,
        parameters: dict[str, Any] | None = None,
        privacy_mode: bool = False,
    ) -> PolicyEvaluationResult:
        """Evaluate a proposed tool execution. Returns authoritative ALLOW, DENY, or REQUIRE_APPROVAL."""
        params = parameters or {}

        # 1. Privacy mode check
        if privacy_mode:
            return PolicyEvaluationResult(
                decision=PolicyDecision.DENY,
                reason="Privacy mode is active. Tool execution is disabled.",
                tool_name=tool_name,
                safety_tier=ToolSafetyTier.READ,
            )

        # 2. Tool registration check
        if not self.registry.has_tool(tool_name):
            return PolicyEvaluationResult(
                decision=PolicyDecision.DENY,
                reason=f"Tool '{tool_name}' is not registered in the tool registry.",
                tool_name=tool_name,
                safety_tier=ToolSafetyTier.DESTRUCTIVE,
            )

        tool_def = self.registry.get_tool(tool_name)

        # 3. Safety tier check
        if tool_def.safety_tier == ToolSafetyTier.DESTRUCTIVE:
            return PolicyEvaluationResult(
                decision=PolicyDecision.DENY,
                reason=f"Destructive tool '{tool_name}' is permanently blocked by policy.",
                tool_name=tool_name,
                safety_tier=tool_def.safety_tier,
            )

        if tool_def.safety_tier == ToolSafetyTier.WRITE:
            return PolicyEvaluationResult(
                decision=PolicyDecision.REQUIRE_APPROVAL,
                reason=f"Write action for tool '{tool_name}' requires explicit user approval.",
                tool_name=tool_name,
                safety_tier=tool_def.safety_tier,
            )

        # 4. Parameter inspection and sanitization
        for key, val in params.items():
            if isinstance(val, str):
                # Bounds check
                if len(val) > 100_000:
                    return PolicyEvaluationResult(
                        decision=PolicyDecision.DENY,
                        reason=f"Parameter '{key}' exceeds maximum allowed length of 100,000 characters.",
                        tool_name=tool_name,
                        safety_tier=tool_def.safety_tier,
                    )
                # Check for forbidden shell injection patterns
                for pat in SHELL_INJECTION_PATTERNS:
                    if re.search(pat, val, flags=re.IGNORECASE):
                        return PolicyEvaluationResult(
                            decision=PolicyDecision.DENY,
                            reason=f"Parameter '{key}' contains forbidden shell or execution patterns.",
                            tool_name=tool_name,
                            safety_tier=tool_def.safety_tier,
                        )

        # 5. Specialized parameter checks for filesystem tools
        if tool_name == "fs.read_text":
            path_val = params.get("path")
            if not path_val or not isinstance(path_val, str):
                return PolicyEvaluationResult(
                    decision=PolicyDecision.DENY,
                    reason="fs.read_text requires a non-empty string 'path' parameter.",
                    tool_name=tool_name,
                    safety_tier=tool_def.safety_tier,
                )
            is_ok, _, reason = self.fs_guard.validate_path(path_val)
            if not is_ok:
                return PolicyEvaluationResult(
                    decision=PolicyDecision.DENY,
                    reason=f"Filesystem policy denied access: {reason}",
                    tool_name=tool_name,
                    safety_tier=tool_def.safety_tier,
                )

        if tool_name == "fs.search":
            dir_val = params.get("directory")
            if dir_val and isinstance(dir_val, str):
                is_ok, _, reason = self.fs_guard.validate_path(dir_val, allow_dir=True)
                if not is_ok:
                    return PolicyEvaluationResult(
                        decision=PolicyDecision.DENY,
                        reason=f"Filesystem policy denied directory access: {reason}",
                        tool_name=tool_name,
                        safety_tier=tool_def.safety_tier,
                    )

        # 6. Safe READ tier passes
        if tool_def.safety_tier == ToolSafetyTier.READ:
            return PolicyEvaluationResult(
                decision=PolicyDecision.ALLOW,
                reason=f"Tool '{tool_name}' verified as safe READ-tier action.",
                tool_name=tool_name,
                safety_tier=tool_def.safety_tier,
            )

        # Default fallback is strictly DENY
        return PolicyEvaluationResult(
            decision=PolicyDecision.DENY,
            reason=f"Default policy denied execution of tool '{tool_name}'.",
            tool_name=tool_name,
            safety_tier=tool_def.safety_tier,
        )
