"""Unit tests for the TaskPlanner generating structured, typed, and validated plans."""

from backend.app.agent.planner import TaskPlanner
from backend.app.agent.schema import TaskIntent, TaskPlan


def test_planner_creates_conversation_plan() -> None:
    planner = TaskPlanner()
    plan = planner.create_plan("Hello Cindercrest, how are you?")
    assert isinstance(plan, TaskPlan)
    assert plan.intent == TaskIntent.CONVERSATION
    assert len(plan.steps) == 0


def test_planner_creates_information_plan_time() -> None:
    planner = TaskPlanner()
    plan = planner.create_plan("What time is it right now?")
    assert isinstance(plan, TaskPlan)
    assert plan.intent == TaskIntent.INFORMATION
    assert len(plan.steps) == 1
    assert plan.steps[0].tool_name == "datetime_now"
    assert plan.steps[0].step_index == 1


def test_planner_creates_information_plan_calculation() -> None:
    planner = TaskPlanner()
    plan = planner.create_plan("Calculate 45 * 12")
    assert isinstance(plan, TaskPlan)
    assert plan.intent == TaskIntent.INFORMATION
    assert len(plan.steps) == 1
    assert plan.steps[0].tool_name == "calculator"
    assert plan.steps[0].parameters.get("expression") == "45 * 12"


def test_planner_creates_information_plan_system_diagnostics() -> None:
    planner = TaskPlanner()
    plan = planner.create_plan("Show me system specs")
    assert isinstance(plan, TaskPlan)
    assert plan.intent == TaskIntent.INFORMATION
    assert len(plan.steps) == 1
    assert plan.steps[0].tool_name == "system_diagnostics"


def test_planner_creates_task_execution_multi_step_plan() -> None:
    planner = TaskPlanner()
    plan = planner.create_plan("Calculate 50 * 2, then check the current time")
    assert isinstance(plan, TaskPlan)
    assert plan.intent == TaskIntent.TASK_EXECUTION
    assert len(plan.steps) == 2
    assert plan.steps[0].tool_name == "calculator"
    assert plan.steps[0].parameters.get("expression") == "50 * 2"
    assert plan.steps[1].tool_name == "datetime_now"
    assert plan.steps[1].step_index == 2
