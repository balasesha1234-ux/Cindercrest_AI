"""Unit tests for the MemoryRetriever ensuring relevance, provenance tagging, and privacy."""

from pathlib import Path

import pytest

from backend.app.memory.retriever import MemoryRetriever
from backend.app.memory.schema import MemoryCategory, MemoryItem
from backend.app.memory.store import MemoryStore
from backend.app.store.db import init_db


@pytest.fixture
def store(tmp_path: Path) -> MemoryStore:
    db_file = tmp_path / "test_retriever.db"
    db_url = f"sqlite:///{db_file}"
    init_db(db_url)
    return MemoryStore(database_url=db_url)


def test_retriever_ranks_relevant_facts_and_preferences(store: MemoryStore) -> None:
    # 1. Fact about database
    store.save(
        MemoryItem(
            memory_id="mem_1",
            category=MemoryCategory.EXPLICIT_FACT,
            key="database_type",
            content="Cindercrest utilizes SQLite in WAL mode for persistent task storage.",
            confidence=1.0,
            provenance="user_explicit",
        )
    )

    # 2. Preference about theme
    store.save(
        MemoryItem(
            memory_id="mem_2",
            category=MemoryCategory.PREFERENCE,
            key="interface_theme",
            content="Obsidian futuristic dark interface with cyan telemetry accents.",
            confidence=1.0,
            provenance="user_explicit",
        )
    )

    # 3. Model inference with moderate confidence
    store.save(
        MemoryItem(
            memory_id="mem_3",
            category=MemoryCategory.INFERENCE,
            key="preferred_work_hours",
            content="User appears to do coding sessions mostly in the early afternoon.",
            confidence=0.75,
            provenance="inference:session_turn",
        )
    )

    retriever = MemoryRetriever(store=store)

    # Query about database storage
    db_results = retriever.retrieve_context("What database does Cindercrest use for storage?")
    assert len(db_results) >= 1
    assert db_results[0].key == "database_type"
    assert "SQLite" in db_results[0].content

    # Query about UI style
    ui_results = retriever.retrieve_context("Tell me about my preferred interface theme")
    assert len(ui_results) >= 1
    assert ui_results[0].key == "interface_theme"


def test_retriever_formats_provenance_and_inference_tags(store: MemoryStore) -> None:
    store.save(
        MemoryItem(
            memory_id="mem_fact",
            category=MemoryCategory.EXPLICIT_FACT,
            key="gpu_model",
            content="NVIDIA RTX 5050 Laptop GPU with 8GB VRAM",
            confidence=1.0,
            provenance="user_explicit",
        )
    )
    store.save(
        MemoryItem(
            memory_id="mem_inf",
            category=MemoryCategory.INFERENCE,
            key="coding_style",
            content="Prefers functional async programming patterns in Python.",
            confidence=0.8,
            provenance="inference:turn_12",
        )
    )

    retriever = MemoryRetriever(store=store)
    context_str = retriever.format_context_for_prompt("What GPU do I have and what is my coding style?")

    assert "[REMEMBERED FACT]" in context_str
    assert "NVIDIA RTX 5050" in context_str
    assert "[INFERENCE (confidence: 0.8)]" in context_str
    assert "functional async programming" in context_str


def test_privacy_mode_blocks_retrieval(store: MemoryStore) -> None:
    store.save(
        MemoryItem(
            memory_id="mem_secret_fact",
            category=MemoryCategory.EXPLICIT_FACT,
            key="sandbox_path",
            content="D:/CindercrestSandbox",
            confidence=1.0,
            provenance="user_explicit",
        )
    )

    retriever = MemoryRetriever(store=store)
    # When privacy mode is active, retrieval returns nothing
    results = retriever.retrieve_context("Where is the sandbox?", privacy_mode=True)
    assert len(results) == 0

    formatted = retriever.format_context_for_prompt("Where is the sandbox?", privacy_mode=True)
    assert formatted == ""


def test_saved_fact_retrieved_in_later_query_and_excluded_after_deletion(store: MemoryStore) -> None:
    """Demonstrate that a useful saved project fact is retrieved in a later conversation

    and that deleted memory is no longer used by the application's retrieval system.
    """
    # 1. Save project fact
    fact_id = "mem_proj_alpha"
    store.save(
        MemoryItem(
            memory_id=fact_id,
            category=MemoryCategory.PROJECT_STATE,
            key="project apex target port",
            content="Project APEX runs on port 9000 for telemetry streams.",
            confidence=1.0,
            provenance="user_explicit",
        )
    )

    retriever = MemoryRetriever(store=store)

    # 2. Query in later conversation - verified retrieved
    initial_retrieval = retriever.retrieve_context("What port does project APEX use for telemetry?")
    assert len(initial_retrieval) == 1
    assert initial_retrieval[0].memory_id == fact_id
    assert "9000" in initial_retrieval[0].content

    # 3. Prompt context contains demarcated fact
    context_for_prompt = retriever.format_context_for_prompt("What port does project APEX use for telemetry?")
    assert "[PROJECT STATE]" in context_for_prompt
    assert "9000" in context_for_prompt

    # 4. User deletes the memory
    deleted = store.delete(fact_id)
    assert deleted is True

    # 5. Subsequent retrieval yields nothing
    subsequent_retrieval = retriever.retrieve_context("What port does project APEX use for telemetry?")
    assert len(subsequent_retrieval) == 0

    subsequent_context = retriever.format_context_for_prompt("What port does project APEX use for telemetry?")
    assert subsequent_context == ""
