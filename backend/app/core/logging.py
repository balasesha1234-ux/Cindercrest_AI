"""Structured logging with deterministic secret redaction."""

import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

# Regex patterns matching sensitive tokens, passwords, and API keys
SECRET_PATTERNS = [
    # Authorization header / Bearer tokens
    (re.compile(r"(Bearer\s+)[a-zA-Z0-9_\-\.]{12,}", re.IGNORECASE), r"\1[REDACTED]"),
    (
        re.compile(r"(['\"]?authorization['\"]?\s*[:=]\s*['\"]?)[^\s'\",]{12,}", re.IGNORECASE),
        r"\1[REDACTED]",
    ),
    # Common API key formats
    (re.compile(r"\bsk-[a-zA-Z0-9_\-]{16,}\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"\bgsk_[a-zA-Z0-9_\-]{20,}\b"), "[REDACTED_GROQ_KEY]"),
    (re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b"), "[REDACTED_GEMINI_KEY]"),
    # URL query parameters
    (
        re.compile(r"([?&](?:token|key|api_key|secret|password)=)[^&\s]+", re.IGNORECASE),
        r"\1[REDACTED]",
    ),
    # JSON password / secret fields
    (
        re.compile(
            r"(['\"](?:password|secret|token|api_key)['\"]\s*:\s*['\"])[^'\"]+(['\"])",
            re.IGNORECASE,
        ),
        r"\1[REDACTED]\2",
    ),
]


def redact_secrets(text: str) -> str:
    """Scrub sensitive keys and tokens from a string."""
    if not isinstance(text, str):
        return text
    redacted = text
    for pattern, replacement in SECRET_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


class SecretRedactingFilter(logging.Filter):
    """Logging filter that scrubs sensitive strings from all log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_secrets(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: redact_secrets(v) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    redact_secrets(arg) if isinstance(arg, str) else arg for arg in record.args
                )
        return True


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects with timestamps and metadata."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_secrets(record.getMessage()),
        }
        if record.exc_info:
            log_data["exception"] = redact_secrets(self.formatException(record.exc_info))
        return json.dumps(log_data)


def setup_logging(debug: bool = False) -> None:
    """Configure application logging with secret redaction and JSON output."""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if debug else logging.INFO)

    # Remove existing handlers to prevent duplicate logs
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG if debug else logging.INFO)
    handler.addFilter(SecretRedactingFilter())
    handler.setFormatter(JSONFormatter())

    root_logger.addHandler(handler)

    # Quiet overly verbose third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("starlette").setLevel(logging.WARNING)


logger = logging.getLogger("cindercrest")
