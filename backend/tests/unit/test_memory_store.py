"""Unit tests for the Controlled MemoryStore enforcing provenance, retention, and corrections."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from backend.app.memory.schema import MemoryCategory, MemoryItem, MemoryStatus
from backend.app.memory.store import MemoryStore
from backend.app.store.db import get_db_connection, init_db


@pytest.fixture
def temp_db(tmp_path: Path) -> str:
    db_file = tmp_path / "test_memory.db"
    db_url = f"sqlite:///{db_file}"
    init_db(db_url)
    return db_url


def test_save_and_retrieve_explicit_fact(temp_db: str) -> None:
    store = MemoryStore(database_url=temp_db)
    item = MemoryItem(
        memory_id="mem_fact_001",
        category=MemoryCategory.EXPLICIT_FACT,
        key="project_codename",
        content="The internal codename for the audio pipeline is Project Apex.",
        confidence=1.0,
        provenance="user_explicit",
    )
    saved = store.save(item)
    assert saved.memory_id == "mem_fact_001"
    assert saved.status == MemoryStatus.ACTIVE

    retrieved = store.get("mem_fact_001")
    assert retrieved is not None
    assert retrieved.content == item.content
    assert retrieved.provenance == "user_explicit"
    assert retrieved.confidence == 1.0


def test_memory_correction_chains_superseded_by(temp_db: str) -> None:
    store = MemoryStore(database_url=temp_db)
    # Original fact
    orig = MemoryItem(
        memory_id="mem_pref_001",
        category=MemoryCategory.PREFERENCE,
        key="preferred_voice",
        content="Microsoft David",
        confidence=1.0,
        provenance="user_explicit",
    )
    store.save(orig)

    # User corrects preference
    corrected = store.correct(
        memory_id="mem_pref_001",
        new_content="Microsoft Heera",
        provenance="user_correction",
    )
    assert corrected.content == "Microsoft Heera"
    assert corrected.key == "preferred_voice"
    assert corrected.category == MemoryCategory.PREFERENCE

    # Verify original is marked as CORRECTED and links to new item
    old_item = store.get("mem_pref_001")
    assert old_item is not None
    assert old_item.status == MemoryStatus.CORRECTED
    assert old_item.superseded_by == corrected.memory_id

    # Active listing returns only the corrected item
    active_items = store.list_memories(category=MemoryCategory.PREFERENCE)
    assert len(active_items) == 1
    assert active_items[0].memory_id == corrected.memory_id
    assert active_items[0].content == "Microsoft Heera"


def test_memory_deletion_prevents_retrieval(temp_db: str) -> None:
    store = MemoryStore(database_url=temp_db)
    item = MemoryItem(
        memory_id="mem_del_001",
        category=MemoryCategory.EXPLICIT_FACT,
        key="temporary_secret",
        content="Temporary staging key",
        confidence=1.0,
        provenance="user_explicit",
    )
    store.save(item)

    # Delete memory
    assert store.delete("mem_del_001", hard=False) is True

    # Get shows deleted or list excludes it
    del_item = store.get("mem_del_001")
    assert del_item is not None
    assert del_item.status == MemoryStatus.DELETED

    active_items = store.list_memories()
    assert all(m.memory_id != "mem_del_001" for m in active_items)


def test_conflicting_facts_auto_supersedes_older_fact(temp_db: str) -> None:
    store = MemoryStore(database_url=temp_db)
    # Save first fact for key "project_lead"
    item1 = MemoryItem(
        memory_id="mem_fact_v1",
        category=MemoryCategory.EXPLICIT_FACT,
        key="project_lead",
        content="Alice is the lead architect.",
        confidence=1.0,
        provenance="conversation_turn",
    )
    store.save(item1)

    # Save conflicting new fact with same key
    item2 = MemoryItem(
        memory_id="mem_fact_v2",
        category=MemoryCategory.EXPLICIT_FACT,
        key="project_lead",
        content="Bob is the new lead architect.",
        confidence=1.0,
        provenance="conversation_turn",
    )
    store.save(item2)

    # Older item is marked as corrected / superseded
    old_item = store.get("mem_fact_v1")
    assert old_item is not None
    assert old_item.status == MemoryStatus.CORRECTED
    assert old_item.superseded_by == "mem_fact_v2"

    active_items = store.list_memories(category=MemoryCategory.EXPLICIT_FACT)
    assert len(active_items) == 1
    assert active_items[0].content == "Bob is the new lead architect."


def test_temporary_observation_ttl_expiration(temp_db: str) -> None:
    store = MemoryStore(database_url=temp_db)
    past_time = datetime.now(UTC) - timedelta(minutes=10)

    # Expired observation
    expired_item = MemoryItem(
        memory_id="mem_temp_expired",
        category=MemoryCategory.TEMPORARY_OBSERVATION,
        key="window_focus",
        content="User focused Spotify at 10:00",
        confidence=0.9,
        provenance="temporary_sensor",
        expires_at=past_time,
    )
    store.save(expired_item)

    # Future observation
    future_time = datetime.now(UTC) + timedelta(hours=1)
    valid_item = MemoryItem(
        memory_id="mem_temp_valid",
        category=MemoryCategory.TEMPORARY_OBSERVATION,
        key="active_ide",
        content="VS Code is currently open",
        confidence=0.9,
        provenance="temporary_sensor",
        expires_at=future_time,
    )
    store.save(valid_item)

    # Purge expired items
    purged_count = store.purge_expired()
    assert purged_count == 1

    active_items = store.list_memories(category=MemoryCategory.TEMPORARY_OBSERVATION)
    assert len(active_items) == 1
    assert active_items[0].memory_id == "mem_temp_valid"


def test_privacy_mode_blocks_saving(temp_db: str) -> None:
    store = MemoryStore(database_url=temp_db)
    item = MemoryItem(
        memory_id="mem_priv_001",
        category=MemoryCategory.PREFERENCE,
        key="theme",
        content="dark",
        confidence=1.0,
        provenance="user_explicit",
    )
    with pytest.raises(PermissionError, match="Privacy Mode"):
        store.save(item, privacy_mode=True)

    assert store.get("mem_priv_001") is None


def test_secret_redaction_in_saved_memory(temp_db: str) -> None:
    store = MemoryStore(database_url=temp_db)
    planted_secret = "sk-live-9999888877776666555544443333"
    item = MemoryItem(
        memory_id="mem_sec_001",
        category=MemoryCategory.EXPLICIT_FACT,
        key="api_credential",
        content=f"The auth token is Bearer {planted_secret}",
        confidence=1.0,
        provenance="user_explicit",
    )
    saved = store.save(item)
    assert planted_secret not in saved.content
    assert "[REDACTED]" in saved.content

    # Check raw DB row
    with get_db_connection(temp_db) as conn:
        row = conn.execute("SELECT content FROM memories WHERE memory_id = ?", ("mem_sec_001",)).fetchone()
        assert row is not None
        assert planted_secret not in row[0]
