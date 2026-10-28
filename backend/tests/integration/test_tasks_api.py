"""Integration tests for the Tasks and Agent Brain REST API endpoints."""

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import get_settings
from backend.app.main import create_app
from backend.app.store.db import init_db


@pytest.fixture
def client(tmp_path: Path) -> Generator[TestClient, None, None]:
    db_file = tmp_path / "test_api_tasks.db"
    db_url = f"sqlite:///{db_file}"
    init_db(db_url)

    settings = get_settings()
    settings.DATABASE_URL = db_url

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_unauthorized_task_request_rejected(client: TestClient) -> None:
    res = client.post("/api/v1/tasks", json={"goal": "What time is it?"})
    assert res.status_code == 401


def test_create_and_execute_task_flow(client: TestClient) -> None:
    settings = get_settings()
    headers = {"Authorization": f"Bearer {settings.SESSION_TOKEN}"}

    # 1. Create task
    create_res = client.post(
        "/api/v1/tasks",
        json={"goal": "Calculate 25 * 4, then check the current time"},
        headers=headers,
    )
    assert create_res.status_code == 201
    data = create_res.json()
    assert "task_id" in data
    task_id = data["task_id"]
    assert data["state"] in ("CREATED", "PLANNING")
    assert len(data["plan"]["steps"]) == 2

    # 2. Execute task
    exec_res = client.post(f"/api/v1/tasks/{task_id}/execute", headers=headers)
    assert exec_res.status_code == 200
    exec_data = exec_res.json()
    assert exec_data["state"] == "COMPLETED"
    assert exec_data["outcome"] == "success"

    # 3. Retrieve task details
    get_res = client.get(f"/api/v1/tasks/{task_id}", headers=headers)
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["task_id"] == task_id
    assert get_data["current_step_index"] == 2

    # 4. Retrieve audit events
    events_res = client.get(f"/api/v1/tasks/{task_id}/events", headers=headers)
    assert events_res.status_code == 200
    events = events_res.json()
    assert len(events) >= 6
    types = [e["event_type"] for e in events]
    assert "TASK_CREATED" in types
    assert "OUTCOME_VERIFIED" in types
    assert "TASK_COMPLETED" in types


def test_list_tasks_and_tools_endpoints(client: TestClient) -> None:
    settings = get_settings()
    headers = {"Authorization": f"Bearer {settings.SESSION_TOKEN}"}

    # List tools
    tools_res = client.get("/api/v1/tools", headers=headers)
    assert tools_res.status_code == 200
    tools = tools_res.json()
    tool_names = [t["name"] for t in tools]
    assert "datetime_now" in tool_names
    assert "calculator" in tool_names
    assert "system_diagnostics" in tool_names
    assert "text_analyzer" in tool_names

    # List tasks
    tasks_res = client.get("/api/v1/tasks", headers=headers)
    assert tasks_res.status_code == 200
    assert isinstance(tasks_res.json(), list)


def test_cancel_task_endpoint(client: TestClient) -> None:
    settings = get_settings()
    headers = {"Authorization": f"Bearer {settings.SESSION_TOKEN}"}

    # Create task
    create_res = client.post(
        "/api/v1/tasks",
        json={"goal": "What time is it?"},
        headers=headers,
    )
    task_id = create_res.json()["task_id"]

    # Cancel task
    cancel_res = client.post(f"/api/v1/tasks/{task_id}/cancel", headers=headers)
    assert cancel_res.status_code == 200
    assert cancel_res.json()["state"] == "CANCELLED"
    assert cancel_res.json()["outcome"] == "cancelled"
