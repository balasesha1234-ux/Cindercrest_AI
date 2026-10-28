"""Authentication and security dependencies for Cindercrest 2.0."""

import secrets

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.core.config import Settings, get_settings
from backend.app.core.exceptions import UnauthorizedError

# We set auto_error=False so we can provide our standardized StandardErrorResponse
bearer_scheme = HTTPBearer(auto_error=False)


def verify_session_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> str:
    """Validate the per-launch Bearer token on protected routes using constant-time comparison."""
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError(message="Authorization header with Bearer token is required")

    provided_token = credentials.credentials.strip()
    expected_token = settings.SESSION_TOKEN.strip()

    if not secrets.compare_digest(provided_token, expected_token):
        raise UnauthorizedError(message="Invalid or expired session token")

    return provided_token
