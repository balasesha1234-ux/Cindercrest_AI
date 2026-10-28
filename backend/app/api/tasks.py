"""REST API endpoints for Cindercrest Agent Brain tasks and tool capabilities."""

from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from backend.app.agent.orchestrator import task_orchestrator
from backend.app.agent.schema import Task, ToolSafetyTier
from backend.app.agent.tools.registry import tool_registry
from backend.app.core.security import verify_session_token

router = APIRouter(prefix="/api/v1", tags=["tasks"])


class CreateTaskRequest(BaseModel):
    """Payload for submitting a new agent task goal."""

    goal: str = Field(min_length=1, max_length=2000, description="Task goal or prompt")


class ToolInfoResponse(BaseModel):
    """Metadata regarding an available tool capability."""

    name: str
    description: str
    safety_tier: ToolSafetyTier
    parameters_schema: dict[str, Any]


@router.post(
    "/tasks",
    response_model=Task,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_session_token)],
)
async def create_task(payload: CreateTaskRequest) -> Task:
    """Create a new task, determine intent, generate and persist structured execution plan."""
    return task_orchestrator.create_task(payload.goal)


@router.post(
    "/tasks/{task_id}/execute",
    response_model=Task,
    dependencies=[Depends(verify_session_token)],
)
async def execute_task(task_id: str) -> Task:
    """Execute a planned task through deterministic policy, tool, and verification gates."""
    return await task_orchestrator.execute_task(task_id)


@router.get(
    "/tasks",
    response_model=list[Task],
    dependencies=[Depends(verify_session_token)],
)
async def list_tasks(limit: int = Query(default=50, ge=1, le=200)) -> list[Task]:
    """List recent persistent tasks."""
    return task_orchestrator.list_tasks(limit=limit)


@router.get(
    "/tasks/{task_id}",
    response_model=Task,
    dependencies=[Depends(verify_session_token)],
)
async def get_task(task_id: str) -> Task:
    """Get detailed information for a specific task."""
    return task_orchestrator.get_task(task_id)


@router.post(
    "/tasks/{task_id}/cancel",
    response_model=Task,
    dependencies=[Depends(verify_session_token)],
)
async def cancel_task(task_id: str) -> Task:
    """Cancel an active or pending task."""
    return task_orchestrator.cancel_task(task_id)


@router.get(
    "/tasks/{task_id}/events",
    response_model=list[dict[str, Any]],
    dependencies=[Depends(verify_session_token)],
)
async def get_task_events(task_id: str) -> list[dict[str, Any]]:
    """Retrieve the append-only audit event log for a task."""
    return task_orchestrator.get_task_events(task_id)


@router.get(
    "/tools",
    response_model=list[ToolInfoResponse],
    dependencies=[Depends(verify_session_token)],
)
async def list_tools() -> list[ToolInfoResponse]:
    """List all registered tools, their parameters, and safety tiers."""
    tools = tool_registry.list_tools()
    return [
        ToolInfoResponse(
            name=t.name,
            description=t.description,
            safety_tier=t.safety_tier,
            parameters_schema=t.parameters_schema,
        )
        for t in tools
    ]
