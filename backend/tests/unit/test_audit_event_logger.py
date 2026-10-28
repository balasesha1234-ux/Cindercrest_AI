"""Unit tests for the AuditEventLogger ensuring append-only persistence and secret redaction."""

from pathlib import Path

from backend.app.agent.events import AuditEventLogger
from backend.app.agent.schema import AuditEventType
from backend.app.store.db import get_db_connection, init_db


def test_audit_event_logging_and_retrieval(tmp_path: Path) -> None:
    db_file = tmp_path / "test_events.db"
    db_url = f"sqlite:///{db_file}"
    init_db(db_url)

    logger = AuditEventLogger(database_url=db_url)
    task_id = "task_test_001"

    # Insert initial task so foreign key constraint is satisfied if enforced
    with get_db_connection(db_url) as conn:
        conn.execute(
            """
            INSERT INTO tasks (task_id, goal, intent_type, state, outcome, plan_json, current_step_index, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                task_id,
                "Test goal",
                "TASK_EXECUTION",
                "CREATED",
                "unknown",
                "{}",
                0,
                "2026-10-28T00:00:00",
                "2026-10-28T00:00:00",
            ),
        )
        conn.commit()

    event_id1 = logger.log_event(task_id, AuditEventType.TASK_CREATED, {"goal": "Test goal"})
    assert event_id1 > 0

    event_id2 = logger.log_event(
        task_id,
        AuditEventType.STEP_STARTED,
        {"step_index": 1, "tool": "datetime_now"},
    )
    assert event_id2 > event_id1

    events = logger.get_events_for_task(task_id)
    assert len(events) == 2
    assert events[0]["event_type"] == AuditEventType.TASK_CREATED
    assert events[0]["payload"]["goal"] == "Test goal"
    assert events[1]["event_type"] == AuditEventType.STEP_STARTED


def test_audit_event_redacts_secrets_in_payload(tmp_path: Path) -> None:
    db_file = tmp_path / "test_redaction.db"
    db_url = f"sqlite:///{db_file}"
    init_db(db_url)

    logger = AuditEventLogger(database_url=db_url)
    task_id = "task_secret_002"

    with get_db_connection(db_url) as conn:
        conn.execute(
            """
            INSERT INTO tasks (task_id, goal, intent_type, state, outcome, plan_json, current_step_index, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                task_id,
                "Redact secret",
                "TASK_EXECUTION",
                "CREATED",
                "unknown",
                "{}",
                0,
                "2026-10-28T00:00:00",
                "2026-10-28T00:00:00",
            ),
        )
        conn.commit()

    planted_secret = "sk-live-abcdef1234567890abcdef12345678"
    logger.log_event(
        task_id,
        AuditEventType.TOOL_EXECUTED,
        {"api_token": planted_secret, "header": f"Bearer {planted_secret}"},
    )

    # Read raw database row
    with get_db_connection(db_url) as conn:
        row = conn.execute(
            "SELECT payload_json FROM task_events WHERE task_id = ?", (task_id,)
        ).fetchone()
        assert row is not None
        raw_json = row[0]
        assert planted_secret not in raw_json
        assert "[REDACTED]" in raw_json
