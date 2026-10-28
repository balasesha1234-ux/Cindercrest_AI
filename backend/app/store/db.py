"""SQLite storage engine with Write-Ahead Logging (WAL) and migrations."""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from backend.app.core.config import get_settings
from backend.app.core.logging import logger


def get_sqlite_path_from_url(database_url: str) -> Path:
    """Parse a sqlite:/// URL into a local Path."""
    if database_url.startswith("sqlite:///"):
        raw_path = database_url.replace("sqlite:///", "")
        return Path(raw_path).resolve()
    return Path("./data/cindercrest.db").resolve()


def init_db(database_url: str | None = None) -> Path:
    """Initialize SQLite database directory and run base migrations."""
    settings = get_settings()
    url = database_url or settings.DATABASE_URL
    db_path = get_sqlite_path_from_url(url)

    # Ensure parent directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        # Enable WAL mode for high concurrent throughput
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")

        # Base tables
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversation_turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                turn_index INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                outcome TEXT NOT NULL DEFAULT 'unknown',
                latency_ms REAL,
                created_at TEXT NOT NULL
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS voice_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                goal TEXT NOT NULL,
                intent_type TEXT NOT NULL,
                state TEXT NOT NULL,
                outcome TEXT NOT NULL DEFAULT 'unknown',
                plan_json TEXT,
                current_step_index INTEGER NOT NULL DEFAULT 0,
                error_message TEXT,
                result_summary TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS task_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (task_id) REFERENCES tasks (task_id)
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                memory_id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                key TEXT NOT NULL,
                content TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 1.0,
                provenance TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                superseded_by TEXT,
                expires_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_cat_key ON memories (category, key);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_status ON memories (status);")

        # Record migration version 1 & 2
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = 1")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (1, ?)",
                (datetime.now(UTC).isoformat(),),
            )
        cursor.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = 2")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (2, ?)",
                (datetime.now(UTC).isoformat(),),
            )
        cursor.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = 3")
        if cursor.fetchone()[0] == 0:
            # Add result_summary if table already existed without it
            cursor.execute(
                "SELECT COUNT(*) FROM pragma_table_info('tasks') WHERE name = 'result_summary'"
            )
            if cursor.fetchone()[0] == 0:
                conn.execute("ALTER TABLE tasks ADD COLUMN result_summary TEXT")
            cursor.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (3, ?)",
                (datetime.now(UTC).isoformat(),),
            )
        cursor.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = 4")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (4, ?)",
                (datetime.now(UTC).isoformat(),),
            )

        # Startup recovery: move any tasks left in running/verifying/planning to OUTCOME_UNKNOWN (AGENTS.md Rule 3 & P1-A)
        conn.execute("""
            UPDATE tasks
            SET state = 'OUTCOME_UNKNOWN', outcome = 'unknown'
            WHERE state IN ('RUNNING', 'PLANNING', 'VERIFYING')
        """)

        conn.execute("""
            UPDATE conversation_turns
            SET outcome = 'unknown'
            WHERE outcome IN ('running', 'verifying', 'processing')
        """)
        conn.commit()

    logger.info("Database initialized successfully at %s", db_path)
    return db_path


@contextmanager
def get_db_connection(database_url: str | None = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager yielding a configured SQLite connection."""
    settings = get_settings()
    url = database_url or settings.DATABASE_URL
    db_path = get_sqlite_path_from_url(url)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def check_db_health() -> bool:
    """Verify that SQLite is operational and can execute a simple query."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
            return bool(row and row[0] == 1)
    except Exception as exc:
        logger.error("Database health check failed: %s", exc)
        return False
