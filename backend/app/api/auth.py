"""Authentication verification endpoint."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.app.core.security import verify_session_token

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


class AuthVerifyResponse(BaseModel):
    """Response returned upon successful token verification."""

    authenticated: bool
    session_active: bool
    token_prefix: str


@router.get("/verify", response_model=AuthVerifyResponse)
async def verify_auth(token: str = Depends(verify_session_token)) -> AuthVerifyResponse:
    """Protected endpoint validating that the caller holds a valid per-launch session token."""
    return AuthVerifyResponse(
        authenticated=True,
        session_active=True,
        token_prefix=token[:6] + "...",
    )
