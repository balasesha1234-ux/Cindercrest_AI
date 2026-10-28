"""Unit tests for configuration loading and validation."""

import pytest
from pydantic import ValidationError

from backend.app.core.config import Settings


def test_localhost_binding_enforced() -> None:
    """Verify that binding to non-localhost addresses raises a validation error."""
    # 127.0.0.1 and localhost are permitted
    s1 = Settings(HOST="127.0.0.1")
    assert s1.HOST == "127.0.0.1"

    s2 = Settings(HOST="localhost")
    assert s2.HOST == "localhost"

    # 0.0.0.0 or external IPs must be rejected
    with pytest.raises(ValidationError) as exc:
        Settings(HOST="0.0.0.0")
    assert "Security violation" in str(exc.value)

    with pytest.raises(ValidationError) as exc:
        Settings(HOST="192.168.1.5")
    assert "Security violation" in str(exc.value)


def test_cors_origin_parsing() -> None:
    """Verify that comma-separated origin strings are parsed into lists."""
    s = Settings(CORS_ORIGINS="http://localhost:3000, http://127.0.0.1:3000")
    assert s.CORS_ORIGINS == ["http://localhost:3000", "http://127.0.0.1:3000"]


def test_session_token_auto_generation() -> None:
    """Verify that an empty or whitespace session token generates a 32-byte hex token."""
    s = Settings(SESSION_TOKEN="")
    assert len(s.SESSION_TOKEN) == 64  # 32 bytes hex = 64 characters
