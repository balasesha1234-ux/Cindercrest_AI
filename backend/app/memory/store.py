"""Persistent, privacy-aware SQLite memory store with conflict resolution and provenance tracking."""

import secrets
import sqlite3
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from backend.app.core.exceptions import NotFoundError
from backend.app.core.logging import redact_secrets
from backend.app.memory.schema import MemoryCategory, MemoryItem, MemoryStatus
from backend.app.store.db import get_db_connection


class MemoryStore:
    """Manages persistent memory items adhering strictly to privacy, provenance, and retention laws."""

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url

    def save(self, item: MemoryItem, privacy_mode: bool = False) -> MemoryItem:
        """Store a memory item with secret redaction and automatic superseding on conflict."""
        if privacy_mode:
            raise PermissionError("Privacy Mode is active. Memory writes are strictly disabled.")

        scrubbed_content = redact_secrets(item.content)
        scrubbed_key = redact_secrets(item.key)

        now_iso = datetime.now(UTC).isoformat()
        expires_str = item.expires_at.isoformat() if item.expires_at else None

        with get_db_connection(self.database_url) as conn:
            # Conflict resolution: if an active item with identical category and key exists, supersede it
            cursor = conn.cursor()
            existing = cursor.execute(
                """
                SELECT memory_id FROM memories
                WHERE category = ? AND key = ? AND status = 'active'
                """,
                (item.category.value, scrubbed_key),
            ).fetchone()

            if existing:
                old_id = existing["memory_id"]
                cursor.execute(
                    """
                    UPDATE memories
                    SET status = 'corrected', superseded_by = ?, updated_at = ?
                    WHERE memory_id = ?
                    """,
                    (item.memory_id, now_iso, old_id),
                )

            cursor.execute(
                """
                INSERT INTO memories (
                    memory_id, category, key, content, confidence, provenance, status, superseded_by, expires_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.memory_id,
                    item.category.value,
                    scrubbed_key,
                    scrubbed_content,
                    item.confidence,
                    item.provenance,
                    item.status.value,
                    item.superseded_by,
                    expires_str,
                    item.created_at.isoformat(),
                    item.updated_at.isoformat(),
                ),
            )
            conn.commit()

        item.content = scrubbed_content
        item.key = scrubbed_key
        return item

    def correct(
        self,
        memory_id: str,
        new_content: str,
        provenance: str = "user_correction",
        privacy_mode: bool = False,
    ) -> MemoryItem:
        """Correct an existing memory, creating a superseding chain."""
        if privacy_mode:
            raise PermissionError("Privacy Mode is active. Memory writes are strictly disabled.")

        old_item = self.get(memory_id)
        if not old_item or old_item.status != MemoryStatus.ACTIVE:
            raise NotFoundError(message=f"Active memory '{memory_id}' not found for correction")

        new_id = f"mem_{int(time.time())}_{secrets.token_hex(4)}"
        now = datetime.now(UTC)

        new_item = MemoryItem(
            memory_id=new_id,
            category=old_item.category,
            key=old_item.key,
            content=new_content,
            confidence=1.0,
            provenance=provenance,
            status=MemoryStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )

        with get_db_connection(self.database_url) as conn:
            conn.execute(
                """
                UPDATE memories
                SET status = 'corrected', superseded_by = ?, updated_at = ?
                WHERE memory_id = ?
                """,
                (new_id, now.isoformat(), memory_id),
            )
            conn.commit()

        return self.save(new_item, privacy_mode=False)

    def delete(self, memory_id: str, hard: bool = False) -> bool:
        """Delete a memory item (soft delete by default)."""
        now_iso = datetime.now(UTC).isoformat()
        with get_db_connection(self.database_url) as conn:
            if hard:
                cursor = conn.execute("DELETE FROM memories WHERE memory_id = ?", (memory_id,))
            else:
                cursor = conn.execute(
                    "UPDATE memories SET status = 'deleted', updated_at = ? WHERE memory_id = ?",
                    (now_iso, memory_id),
                )
            conn.commit()
            return cursor.rowcount > 0

    def get(self, memory_id: str) -> MemoryItem | None:
        """Fetch memory item by ID."""
        with get_db_connection(self.database_url) as conn:
            row = conn.execute(
                """
                SELECT memory_id, category, key, content, confidence, provenance, status, superseded_by, expires_at, created_at, updated_at
                FROM memories
                WHERE memory_id = ?
                """,
                (memory_id,),
            ).fetchone()

            if not row:
                return None

            return self._row_to_item(row)

    def list_memories(
        self,
        category: MemoryCategory | None = None,
        key: str | None = None,
        status: MemoryStatus | None = MemoryStatus.ACTIVE,
        limit: int = 50,
    ) -> list[MemoryItem]:
        """List memories matching category, key, and status filter."""
        query = "SELECT * FROM memories WHERE 1=1"
        params: list[str | int] = []

        if category:
            query += " AND category = ?"
            params.append(category.value)

        if key:
            query += " AND key = ?"
            params.append(redact_secrets(key))

        if status:
            query += " AND status = ?"
            params.append(status.value)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with get_db_connection(self.database_url) as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_item(r) for r in rows]

    def purge_expired(self) -> int:
        """Purge expired temporary observations whose TTL has lapsed."""
        now_iso = datetime.now(UTC).isoformat()
        with get_db_connection(self.database_url) as conn:
            cursor = conn.execute(
                """
                UPDATE memories
                SET status = 'deleted', updated_at = ?
                WHERE status = 'active' AND expires_at IS NOT NULL AND expires_at <= ?
                """,
                (now_iso, now_iso),
            )
            conn.commit()
            return cursor.rowcount

    def _row_to_item(self, row: sqlite3.Row | Mapping[str, Any]) -> MemoryItem:
        r = dict(row)
        expires_raw = r.get("expires_at")
        expires_at = datetime.fromisoformat(str(expires_raw)) if expires_raw else None
        return MemoryItem(
            memory_id=str(r["memory_id"]),
            category=MemoryCategory(str(r["category"])),
            key=str(r["key"]),
            content=str(r["content"]),
            confidence=float(str(r["confidence"])),
            provenance=str(r["provenance"]),
            status=MemoryStatus(str(r["status"])),
            superseded_by=str(r["superseded_by"]) if r.get("superseded_by") else None,
            expires_at=expires_at,
            created_at=datetime.fromisoformat(str(r["created_at"])),
            updated_at=datetime.fromisoformat(str(r["updated_at"])),
        )


memory_store = MemoryStore()
