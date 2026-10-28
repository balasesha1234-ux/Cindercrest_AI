"""Shared test fixtures and environment overrides."""

import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import Settings, get_settings
from backend.app.main import create_app
from backend.app.store.db import init_db

TEST_TOKEN = "cindercrest-test-token-1234567890abcdef"


@pytest.fixture(scope="session")
def temp_db_path() -> Generator[Path, None, None]:
    """Create a temporary SQLite database file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    init_db(f"sqlite:///{db_path}")
    yield db_path

    # Cleanup after test session
    try:
        if db_path.exists():
            db_path.unlink()
        wal_path = Path(str(db_path) + "-wal")
        if wal_path.exists():
            wal_path.unlink()
        shm_path = Path(str(db_path) + "-shm")
        if shm_path.exists():
            shm_path.unlink()
    except Exception:
        pass


@pytest.fixture
def test_settings(temp_db_path: Path) -> Settings:
    """Fixture providing isolated test settings."""
    return Settings(
        HOST="127.0.0.1",
        PORT=8000,
        DEBUG=True,
        SESSION_TOKEN=TEST_TOKEN,
        DATABASE_URL=f"sqlite:///{temp_db_path}",
        OLLAMA_BASE_URL="http://127.0.0.1:11434",
    )


@pytest.fixture
def client(test_settings: Settings) -> Generator[TestClient, None, None]:
    """Test client with overridden dependencies."""
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: test_settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
