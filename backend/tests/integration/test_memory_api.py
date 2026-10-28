"""Integration tests for the Memory REST API and conversational continuity."""

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import get_settings
from backend.app.main import create_app
from backend.app.store.db import init_db


@pytest.fixture
def client(tmp_path: Path) -> Generator[TestClient, None, None]:
    db_file = tmp_path / "test_api_memory.db"
    db_url = f"sqlite:///{db_file}"
    init_db(db_url)

    settings = get_settings()
    settings.DATABASE_URL = db_url

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_unauthorized_memory_request_rejected(client: TestClient) -> None:
    res = client.get("/api/v1/memory")
    assert res.status_code == 401


def test_memory_crud_lifecycle_api(client: TestClient) -> None:
    settings = get_settings()
    headers = {"Authorization": f"Bearer {settings.SESSION_TOKEN}"}

    # 1. Create explicitly saved fact
    create_res = client.post(
        "/api/v1/memory",
        json={
            "category": "explicit_fact",
            "key": "approved_sandbox_root",
            "content": "D:/CindercrestSandbox/reports",
            "confidence": 1.0,
            "provenance": "user_explicit",
        },
        headers=headers,
    )
    assert create_res.status_code == 201
    created_data = create_res.json()
    memory_id = created_data["memory_id"]
    assert created_data["status"] == "active"
    assert created_data["key"] == "approved_sandbox_root"

    # 2. Search / Retrieve memory
    search_res = client.get(
        "/api/v1/memory/search?query=Where is the approved sandbox root?",
        headers=headers,
    )
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert len(search_data) >= 1
    assert search_data[0]["key"] == "approved_sandbox_root"
    assert "D:/CindercrestSandbox/reports" in search_data[0]["content"]

    # 3. Correct memory
    correct_res = client.put(
        f"/api/v1/memory/{memory_id}",
        json={
            "content": "E:/CindercrestSandbox/verified_reports",
            "provenance": "user_correction",
        },
        headers=headers,
    )
    assert correct_res.status_code == 200
    corrected_data = correct_res.json()
    new_memory_id = corrected_data["memory_id"]
    assert new_memory_id != memory_id
    assert corrected_data["content"] == "E:/CindercrestSandbox/verified_reports"

    # 4. Verify search retrieves the corrected memory
    search_v2 = client.get(
        "/api/v1/memory/search?query=approved sandbox",
        headers=headers,
    )
    assert search_v2.status_code == 200
    assert len(search_v2.json()) == 1
    assert search_v2.json()[0]["content"] == "E:/CindercrestSandbox/verified_reports"

    # 5. Delete memory
    del_res = client.delete(f"/api/v1/memory/{new_memory_id}", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True

    # 6. Verify deleted memory is NO LONGER RETRIEVED by search
    search_v3 = client.get(
        "/api/v1/memory/search?query=approved sandbox",
        headers=headers,
    )
    assert search_v3.status_code == 200
    assert len(search_v3.json()) == 0
