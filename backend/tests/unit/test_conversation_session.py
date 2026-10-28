"""Unit tests for conversation session and turn management."""

import pytest

from backend.app.core.exceptions import ValidationError
from backend.app.model.router import ModelRouter
from backend.app.orchestrator.conversation import ConversationSession
from backend.tests.unit.test_model_router import LabeledMockTestProvider


@pytest.mark.asyncio
async def test_execute_turn_lifecycle() -> None:
    """Verify that user turn and assistant reply are recorded in sequence."""
    session = ConversationSession()
    session.clear()

    router = ModelRouter()
    mock_prov = LabeledMockTestProvider(provider_id="test-llm")
    router.register_provider(mock_prov)

    reply_turn = await session.execute_turn(
        "Hello Cindercrest", router=router, provider_id="test-llm"
    )
    assert reply_turn.role == "assistant"
    assert reply_turn.content == "Hello world!"
    assert reply_turn.turn_index == 2
    assert reply_turn.outcome == "success"
    assert reply_turn.latency_ms is not None

    # History should contain exactly 2 turns (user, assistant)
    assert len(session.turns) == 2
    assert session.turns[0].role == "user"
    assert session.turns[0].content == "Hello Cindercrest"
    assert session.turns[1].role == "assistant"


@pytest.mark.asyncio
async def test_empty_user_message_rejected() -> None:
    """Verify that empty or whitespace-only messages raise ValidationError."""
    session = ConversationSession()

    with pytest.raises(ValidationError) as exc:
        await session.execute_turn("   ")
    assert "cannot be empty" in str(exc.value)


@pytest.mark.asyncio
async def test_session_reset() -> None:
    """Verify that session reset clears history and resets counter."""
    session = ConversationSession()
    router = ModelRouter()
    router.register_provider(LabeledMockTestProvider(provider_id="test-llm"))

    await session.execute_turn("Turn 1", router=router, provider_id="test-llm")
    assert len(session.turns) == 2

    session.clear()
    assert len(session.turns) == 0


@pytest.mark.asyncio
async def test_context_window_bounding() -> None:
    """Verify that context window is bounded to max_context_turns."""
    session = ConversationSession(max_context_turns=4)
    session.clear()
    router = ModelRouter()
    router.register_provider(LabeledMockTestProvider(provider_id="test-llm"))

    # Execute 3 user turns (6 total turns: 3 user + 3 assistant)
    for i in range(3):
        await session.execute_turn(f"Question {i + 1}", router=router, provider_id="test-llm")

    assert len(session.turns) == 6
    context = session._get_context_messages()
    assert len(context) == 4
    assert context[-1].content == "Hello world!"


@pytest.mark.asyncio
async def test_secrets_redacted_before_db_persistence() -> None:
    """Verify that planted secrets in user text are never stored unredacted in SQLite (AGENTS.md Rule 7)."""
    session = ConversationSession()
    session.clear()
    router = ModelRouter()
    router.register_provider(LabeledMockTestProvider(provider_id="test-llm"))

    planted_secret = "sk-1234567890abcdef12345678"
    user_input = f"My OpenAI key is {planted_secret}. Help me with it."

    await session.execute_turn(user_input, router=router, provider_id="test-llm")

    from backend.app.store.db import get_db_connection

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT content FROM conversation_turns WHERE role = 'user' ORDER BY id DESC LIMIT 1"
        )
        row = cursor.fetchone()
        assert row is not None
        stored_content = row[0]
        assert planted_secret not in stored_content
        assert "[REDACTED_API_KEY]" in stored_content


@pytest.mark.asyncio
async def test_crash_recovery_resets_in_progress_turns() -> None:
    """Verify that turns left in 'running' or 'processing' are reset to 'unknown' on startup (AGENTS.md Rule 3 & P1-A)."""
    from backend.app.store.db import get_db_connection, init_db

    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO conversation_turns (turn_index, role, content, outcome, created_at)
            VALUES (999, 'assistant', 'Interrupted during generation', 'processing', '2026-10-28T11:00:00Z')
            """
        )
        conn.commit()

    # Re-initialize DB (simulating backend process restart)
    init_db()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT outcome FROM conversation_turns WHERE turn_index = 999")
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "unknown"


@pytest.mark.asyncio
async def test_explicit_remember_saves_to_memory_and_acknowledges() -> None:
    """Verify that 'Remember that ...' automatically persists an explicit fact and acknowledges."""
    from backend.app.memory.store import memory_store

    session = ConversationSession()
    session.clear()
    router = ModelRouter()

    turn = await session.execute_turn(
        "Remember that the project code name is APEX", router=router
    )
    assert turn.role == "assistant"
    assert "I have noted that:" in turn.content
    assert "project code name is APEX" in turn.content

    # Verify stored in memory_store
    active_mems = memory_store.list_memories(key="project code name")
    assert len(active_mems) >= 1
    assert "project code name is APEX" in active_mems[0].content


@pytest.mark.asyncio
async def test_privacy_mode_blocks_remember_in_conversation() -> None:
    """Verify that when privacy_mode=True, memory storage is blocked."""
    session = ConversationSession()
    session.clear()
    router = ModelRouter()

    turn = await session.execute_turn(
        "Remember that secret token is 12345", router=router, privacy_mode=True
    )
    assert "Privacy Mode is currently active" in turn.content
