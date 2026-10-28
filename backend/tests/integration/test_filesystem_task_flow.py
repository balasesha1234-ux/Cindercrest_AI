"""Integration test verifying end-to-end search, read, and summarization of an approved document."""

from pathlib import Path

import pytest

from backend.app.agent.orchestrator import TaskOrchestrator
from backend.app.agent.schema import TaskOutcome, TaskState
from backend.app.store.db import init_db


@pytest.fixture
def temp_db(tmp_path: Path) -> str:
    db_file = tmp_path / "test_fs_flow.db"
    db_url = f"sqlite:///{db_file}"
    init_db(db_url)
    return db_url


@pytest.mark.asyncio
async def test_find_and_read_project_document_flow(temp_db: str) -> None:
    orchestrator = TaskOrchestrator(database_url=temp_db)

    # Submit task to search and read project document
    task = orchestrator.create_task("Find the speech stack assessment document and summarize it")

    assert task.plan is not None
    assert len(task.plan.steps) >= 1
    tool_names = [s.tool_name for s in task.plan.steps]
    assert "fs.search" in tool_names or "fs.read_text" in tool_names

    # Execute task
    finished = await orchestrator.execute_task(task.task_id)

    assert finished.state == TaskState.COMPLETED
    assert finished.outcome == TaskOutcome.SUCCESS
    assert finished.plan is not None
    assert all(step.verified for step in finished.plan.steps)
    assert finished.result_summary is not None
    assert "SPEECH_STACK_ASSESSMENT" in finished.result_summary or "Speech" in finished.result_summary

    # Check that search actually found SPEECH_STACK_ASSESSMENT.md
    search_step = next((s for s in finished.plan.steps if s.tool_name == "fs.search"), None)
    if search_step:
        assert search_step.result is not None
        assert search_step.result["total_found"] >= 1
        found_filenames = [f["filename"] for f in search_step.result["results"]]
        assert any("SPEECH" in fn.upper() for fn in found_filenames)

    # Check that read_step extracted real grounded text
    read_step = next((s for s in finished.plan.steps if s.tool_name == "fs.read_text"), None)
    if read_step:
        assert read_step.result is not None
        content = read_step.result["content"]
        assert len(content) > 100
        # Verify content contains actual text from docs/SPEECH_STACK_ASSESSMENT.md
        assert "Whisper" in content or "TTS" in content or "Speech" in content
