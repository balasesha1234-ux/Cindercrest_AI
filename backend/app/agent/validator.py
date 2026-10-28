"""Plan validator ensuring proposed plans strictly comply with safety policies and schema rules."""

import re

from backend.app.agent.policy import SHELL_INJECTION_PATTERNS
from backend.app.agent.schema import TaskIntent, TaskPlan, ToolSafetyTier
from backend.app.agent.tools.registry import ToolRegistry, tool_registry
from backend.app.core.exceptions import ValidationError


class PlanValidator:
    """Validates TaskPlan structures before execution."""

    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self.registry = registry or tool_registry

    def validate_plan(self, plan: TaskPlan) -> None:
        """Validate a TaskPlan. Raises ValidationError if any check fails."""
        if not plan.goal or not plan.goal.strip():
            raise ValidationError("Plan goal cannot be empty")

        # Conversational intent must not have tool execution steps
        if plan.intent == TaskIntent.CONVERSATION:
            if plan.steps:
                raise ValidationError("Conversational plans must not contain action steps")
            return

        # TASK_EXECUTION requires at least one action step
        if plan.intent == TaskIntent.TASK_EXECUTION and not plan.steps:
            raise ValidationError("Task execution plan requires at least one action step")

        # Validate steps
        expected_step_index = 1
        for step in plan.steps:
            # 1. Step sequence verification
            if step.step_index != expected_step_index:
                raise ValidationError(
                    f"Step indices must be strictly sequential starting at 1. "
                    f"Expected step {expected_step_index}, got {step.step_index}."
                )
            expected_step_index += 1

            # 2. Tool existence check
            if not self.registry.has_tool(step.tool_name):
                raise ValidationError(
                    f"Tool '{step.tool_name}' in step {step.step_index} is not registered."
                )

            tool_def = self.registry.get_tool(step.tool_name)

            # 3. Safety tier check
            if tool_def.safety_tier == ToolSafetyTier.DESTRUCTIVE:
                raise ValidationError(
                    f"Tool '{step.tool_name}' is classified as DESTRUCTIVE and cannot be planned."
                )

            # 4. Parameters validation against tool's parameters_schema
            required_params = tool_def.parameters_schema.get("required", [])

            for req in required_params:
                if req not in step.parameters:
                    raise ValidationError(
                        f"Missing required parameter '{req}' for tool '{step.tool_name}' in step {step.step_index}."
                    )

            # 5. Injection & bounds check on parameter values
            for key, val in step.parameters.items():
                if isinstance(val, str):
                    for pat in SHELL_INJECTION_PATTERNS:
                        if re.search(pat, val, flags=re.IGNORECASE):
                            raise ValidationError(
                                f"Parameter '{key}' in step {step.step_index} contains forbidden patterns: '{val}'"
                            )

            # 6. Expected outcome check
            if not step.expected_outcome or not step.expected_outcome.strip():
                raise ValidationError(
                    f"Step {step.step_index} must specify a non-empty expected outcome."
                )
