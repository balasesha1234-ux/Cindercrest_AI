"""Tests for the TaskOrchestrator managing task lifecycles, execution, and safety."""

from pathlib import Path
from typing import Any

import pytest

from backend.app.agent.orchestrator import TaskOrchestrator
from backend.app.agent.schema import TaskOutcome, TaskState
from backend.app.agent.tools.registry import ToolDefinition, ToolRegistry
from backend.app.core.exceptions import NotFoundError
from backend.app.store.db import get_db_connection, init_db


@pytest.fixture
def temp_db(tmp_path: Path) -> str:
    db_file = tmp_path / "test_orchestrator.db"
    db_url = f"sqlite:///{db_file}"
    init_db(db_url)
    return db_url


@pytest.mark.asyncio
async def test_end_to_end_task_execution(temp_db: str) -> None:
    orchestrator = TaskOrchestrator(database_url=temp_db)
    task = orchestrator.create_task("Calculate 100 / 4, then check the current time")

    assert task.task_id.startswith("task_")
    assert task.state in (TaskState.CREATED, TaskState.PLANNING)
    assert task.plan is not None
    assert len(task.plan.steps) == 2

    # Execute task
    finished_task = await orchestrator.execute_task(task.task_id)

    assert finished_task.state == TaskState.COMPLETED
    assert finished_task.outcome == TaskOutcome.SUCCESS
    assert finished_task.current_step_index == 2
    assert finished_task.plan is not None
    assert all(step.verified for step in finished_task.plan.steps)
    assert all(step.status == "completed" for step in finished_task.plan.steps)

    # Check audit events recorded
    events = orchestrator.get_task_events(task.task_id)
    event_types = [e["event_type"] for e in events]
    assert "TASK_CREATED" in event_types
    assert "PLAN_GENERATED" in event_types
    assert "STEP_STARTED" in event_types
    assert "POLICY_EVALUATED" in event_types
    assert "TOOL_EXECUTED" in event_types
    assert "OUTCOME_VERIFIED" in event_types
    assert "TASK_COMPLETED" in event_types


@pytest.mark.asyncio
async def test_task_denied_by_policy(temp_db: str) -> None:
    orchestrator = TaskOrchestrator(database_url=temp_db)
    task = orchestrator.create_task("Calculate 100 / 4")

    # Manually inject an illegal parameter into the plan to trigger policy denial
    assert task.plan is not None
    task.plan.steps[0].parameters = {"expression": "1 + 1; rm -rf /"}
    orchestrator._save_task(task)

    finished_task = await orchestrator.execute_task(task.task_id)
    assert finished_task.state == TaskState.FAILED
    assert finished_task.outcome == TaskOutcome.FAILURE
    assert finished_task.error_message is not None
    assert (
        "forbidden" in finished_task.error_message.lower()
        or "denied" in finished_task.error_message.lower()
    )


@pytest.mark.asyncio
async def test_task_cancellation(temp_db: str) -> None:
    orchestrator = TaskOrchestrator(database_url=temp_db)
    task = orchestrator.create_task("Show me system specs")

    # Cancel task before execution
    cancelled_task = orchestrator.cancel_task(task.task_id)
    assert cancelled_task.state == TaskState.CANCELLED
    assert cancelled_task.outcome == TaskOutcome.CANCELLED

    # Executing cancelled task should remain cancelled
    res = await orchestrator.execute_task(task.task_id)
    assert res.state == TaskState.CANCELLED


@pytest.mark.asyncio
async def test_uncertain_outcome_yields_outcome_unknown(temp_db: str) -> None:
    # Set up custom registry where a tool returns invalid format
    custom_registry = ToolRegistry()

    async def flaky_datetime(params: dict[str, Any]) -> dict[str, Any]:
        return {"iso_utc": "invalid-garbage-date"}

    custom_registry.register(
        ToolDefinition(
            name="datetime_now",
            description="Flaky time tool",
            parameters_schema={},
            handler=flaky_datetime,
        )
    )

    orchestrator = TaskOrchestrator(database_url=temp_db, registry=custom_registry)
    task = orchestrator.create_task("What time is it right now?")

    finished_task = await orchestrator.execute_task(task.task_id)
    # Attempted is not done: unverifiable output must transition to OUTCOME_UNKNOWN
    assert finished_task.state == TaskState.OUTCOME_UNKNOWN
    assert finished_task.outcome == TaskOutcome.UNKNOWN


@pytest.mark.asyncio
async def test_task_not_found_raises_error(temp_db: str) -> None:
    orchestrator = TaskOrchestrator(database_url=temp_db)
    with pytest.raises(NotFoundError):
        await orchestrator.execute_task("task_non_existent")


def test_startup_recovery_moves_in_flight_tasks_to_unknown(temp_db: str) -> None:
    # Plant tasks in RUNNING, PLANNING, and VERIFYING states
    with get_db_connection(temp_db) as conn:
        for state in ("RUNNING", "PLANNING", "VERIFYING"):
            conn.execute(
                """
                INSERT INTO tasks (
                    task_id, goal, intent_type, state, outcome, plan_json, current_step_index, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    f"task_{state.lower()}",
                    "In-flight task",
                    "TASK_EXECUTION",
                    state,
                    "in_progress",
                    "{}",
                    1,
                    "2026-10-28T00:00:00",
                    "2026-10-28T00:00:00",
                ),
            )
        conn.commit()

    # Re-run startup initialization (simulating service restart after hard crash)
    init_db(temp_db)

    # Verify all in-flight tasks were recovered to OUTCOME_UNKNOWN and outcome unknown
    orchestrator = TaskOrchestrator(database_url=temp_db)
    for state in ("RUNNING", "PLANNING", "VERIFYING"):
        task = orchestrator.get_task(f"task_{state.lower()}")
        assert task.state == TaskState.OUTCOME_UNKNOWN
        assert task.outcome == TaskOutcome.UNKNOWN
