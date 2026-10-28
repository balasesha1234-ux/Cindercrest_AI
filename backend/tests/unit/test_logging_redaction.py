"""Unit tests for secret redaction in logging."""

import logging

from backend.app.core.logging import SecretRedactingFilter, redact_secrets


def test_redact_secrets_bearer_token() -> None:
    """Verify that Bearer tokens are masked."""
    text = "Inbound request with header: Bearer abc123456789xyz_long_token_here"
    redacted = redact_secrets(text)
    assert "abc123456789xyz_long_token_here" not in redacted
    assert "Bearer [REDACTED]" in redacted


def test_redact_secrets_api_keys() -> None:
    """Verify that OpenAI, Groq, and Gemini style API keys are masked."""
    text1 = "Loaded key: sk-abcdefghijklmnopqrstuvwxyz123456"
    assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in redact_secrets(text1)
    assert "[REDACTED_API_KEY]" in redact_secrets(text1)

    text_groq = "Loaded Groq key: gsk_1234567890abcdefghijklmnopqrstuv"
    assert "gsk_1234567890abcdefghijklmnopqrstuv" not in redact_secrets(text_groq)
    assert "[REDACTED_GROQ_KEY]" in redact_secrets(text_groq)

    text2 = "Using Gemini key: AIzaSyD1234567890abcdefghijklmnopqrstuv"
    assert "AIzaSyD1234567890abcdefghijklmnopqrstuv" not in redact_secrets(text2)
    assert "[REDACTED_GEMINI_KEY]" in redact_secrets(text2)


def test_redact_secrets_query_and_json_passwords() -> None:
    """Verify URL query parameters and JSON fields are redacted."""
    url = "http://127.0.0.1:8000/callback?token=super_secret_value_123&user=admin"
    assert "super_secret_value_123" not in redact_secrets(url)
    assert "token=[REDACTED]" in redact_secrets(url)

    json_blob = '{"username": "admin", "password": "MySuperSecretPassword99!"}'
    assert "MySuperSecretPassword99!" not in redact_secrets(json_blob)
    assert '"password": "[REDACTED]"' in redact_secrets(json_blob)


def test_logging_filter_scrubs_record() -> None:
    """Verify that SecretRedactingFilter alters log record messages."""
    redacting_filter = SecretRedactingFilter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="User authenticated with token: Bearer abcdef1234567890secret",
        args=(),
        exc_info=None,
    )
    redacting_filter.filter(record)
    assert "abcdef1234567890secret" not in record.msg
    assert "Bearer [REDACTED]" in record.msg
