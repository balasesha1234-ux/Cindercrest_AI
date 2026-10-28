"""Unit tests for the PlanValidator rejecting malformed, illegal, or injection-laden plans."""

import pytest

from backend.app.agent.schema import ActionStep, TaskIntent, TaskPlan
from backend.app.agent.validator import PlanValidator
from backend.app.core.exceptions import ValidationError


def test_validator_accepts_valid_task_plan() -> None:
    validator = PlanValidator()
    plan = TaskPlan(
        goal="Calculate 25 * 4 and check the current time",
        intent=TaskIntent.TASK_EXECUTION,
        steps=[
            ActionStep(
                step_index=1,
                tool_name="calculator",
                parameters={"expression": "25 * 4"},
                expected_outcome="Arithmetic product equal to 100",
            ),
            ActionStep(
                step_index=2,
                tool_name="datetime_now",
                parameters={},
                expected_outcome="Current timestamp in ISO format",
            ),
        ],
    )
    # Should validate without error
    validator.validate_plan(plan)


def test_validator_accepts_valid_conversation_plan() -> None:
    validator = PlanValidator()
    plan = TaskPlan(
        goal="Hello, how are you?",
        intent=TaskIntent.CONVERSATION,
        steps=[],
    )
    validator.validate_plan(plan)


def test_validator_rejects_empty_steps_for_task_execution() -> None:
    validator = PlanValidator()
    plan = TaskPlan(
        goal="Execute complex diagnostics",
        intent=TaskIntent.TASK_EXECUTION,
        steps=[],
    )
    with pytest.raises(ValidationError, match="requires at least one action step"):
        validator.validate_plan(plan)


def test_validator_rejects_conversation_with_steps() -> None:
    validator = PlanValidator()
    plan = TaskPlan(
        goal="Good morning",
        intent=TaskIntent.CONVERSATION,
        steps=[
            ActionStep(
                step_index=1,
                tool_name="datetime_now",
                parameters={},
                expected_outcome="Current time",
            )
        ],
    )
    with pytest.raises(ValidationError, match="must not contain action steps"):
        validator.validate_plan(plan)


def test_validator_rejects_non_sequential_step_indices() -> None:
    validator = PlanValidator()
    plan = TaskPlan(
        goal="Run calculations",
        intent=TaskIntent.TASK_EXECUTION,
        steps=[
            ActionStep(
                step_index=1,
                tool_name="calculator",
                parameters={"expression": "1 + 1"},
                expected_outcome="Sum is 2",
            ),
            ActionStep(
                step_index=3,  # Skipped step 2!
                tool_name="datetime_now",
                parameters={},
                expected_outcome="Current time",
            ),
        ],
    )
    with pytest.raises(ValidationError, match="Step indices must be strictly sequential"):
        validator.validate_plan(plan)


def test_validator_rejects_unknown_tool() -> None:
    validator = PlanValidator()
    plan = TaskPlan(
        goal="Hack mainframe",
        intent=TaskIntent.TASK_EXECUTION,
        steps=[
            ActionStep(
                step_index=1,
                tool_name="non_existent_tool_xyz",
                parameters={},
                expected_outcome="Breach",
            )
        ],
    )
    with pytest.raises(ValidationError, match="is not registered"):
        validator.validate_plan(plan)


def test_validator_rejects_missing_required_parameters() -> None:
    validator = PlanValidator()
    plan = TaskPlan(
        goal="Calculate something",
        intent=TaskIntent.TASK_EXECUTION,
        steps=[
            ActionStep(
                step_index=1,
                tool_name="calculator",
                parameters={},  # Missing required 'expression' parameter
                expected_outcome="Calculated result",
            )
        ],
    )
    with pytest.raises(ValidationError, match="Missing required parameter"):
        validator.validate_plan(plan)


def test_validator_rejects_injection_parameters() -> None:
    validator = PlanValidator()
    plan = TaskPlan(
        goal="Execute command",
        intent=TaskIntent.TASK_EXECUTION,
        steps=[
            ActionStep(
                step_index=1,
                tool_name="calculator",
                parameters={"expression": "1 + 1; rm -rf /"},
                expected_outcome="Result",
            )
        ],
    )
    with pytest.raises(ValidationError, match="forbidden patterns"):
        validator.validate_plan(plan)
