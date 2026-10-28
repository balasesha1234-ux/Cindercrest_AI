"""Append-only audit event logger for task lifecycle tracking with secret redaction."""

import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from backend.app.agent.schema import AuditEventType
from backend.app.core.logging import redact_secrets
from backend.app.store.db import get_db_connection


class AuditEventLogger:
    """Manages append-only task event trails in SQLite."""

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url

    def log_event(
        self,
        task_id: str,
        event_type: AuditEventType | str,
        payload: dict[str, Any] | BaseModel | str,
    ) -> int:
        """Append an audit event with secret redaction. Returns the created event ID."""
        if isinstance(payload, BaseModel):
            raw_payload = payload.model_dump(mode="json")
        elif isinstance(payload, dict):
            raw_payload = payload
        else:
            raw_payload = {"message": str(payload)}

        payload_json = json.dumps(raw_payload)
        # Apply strict secret redaction law
        scrubbed_json = redact_secrets(payload_json)

        type_str = event_type.value if isinstance(event_type, AuditEventType) else str(event_type)
        now_iso = datetime.now(UTC).isoformat()

        with get_db_connection(self.database_url) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO task_events (task_id, event_type, payload_json, created_at)
                VALUES (?, ?, ?, ?)
            """,
                (task_id, type_str, scrubbed_json, now_iso),
            )
            conn.commit()
            return cursor.lastrowid or 0

    def get_events_for_task(self, task_id: str) -> list[dict[str, Any]]:
        """Retrieve the ordered audit event log for a given task ID."""
        with get_db_connection(self.database_url) as conn:
            rows = conn.execute(
                """
                SELECT id, task_id, event_type, payload_json, created_at
                FROM task_events
                WHERE task_id = ?
                ORDER BY id ASC
            """,
                (task_id,),
            ).fetchall()

            events = []
            for row in rows:
                try:
                    payload_data = json.loads(row["payload_json"])
                except Exception:
                    payload_data = {"raw": row["payload_json"]}

                events.append(
                    {
                        "id": row["id"],
                        "task_id": row["task_id"],
                        "event_type": row["event_type"],
                        "payload": payload_data,
                        "created_at": row["created_at"],
                    }
                )
            return events
