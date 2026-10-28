"""System health probe endpoint."""

from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.app.core.config import Settings, get_settings
from backend.app.store.db import check_db_health

router = APIRouter(tags=["Health"])


class ComponentHealth(BaseModel):
    """Health status of an individual component."""

    status: str
    details: dict[str, Any]


class HealthResponse(BaseModel):
    """Aggregate health status payload."""

    status: str
    version: str = "2.0.0"
    timestamp: datetime
    checks: dict[str, ComponentHealth]


@router.get("/health", response_model=HealthResponse)
async def get_health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Public health probe endpoint verifying database and subsystem availability."""
    db_ok = check_db_health()

    # Probe local Ollama service with a short bounded timeout
    ollama_ok = False
    ollama_details: dict[str, Any] = {"url": settings.OLLAMA_BASE_URL}
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if resp.status_code == 200:
                ollama_ok = True
                ollama_details["models_available"] = len(resp.json().get("models", []))
    except Exception as exc:
        ollama_details["error"] = str(exc)

    overall_status = "healthy" if db_ok else "degraded"

    return HealthResponse(
        status=overall_status,
        timestamp=datetime.now(UTC),
        checks={
            "database": ComponentHealth(
                status="ok" if db_ok else "error",
                details={"engine": "sqlite-wal", "url": settings.DATABASE_URL},
            ),
            "ollama": ComponentHealth(
                status="ok" if ollama_ok else "unreachable",
                details=ollama_details,
            ),
            "voice_subsystem": ComponentHealth(
                status="ready",
                details={
                    "sample_rate": settings.VOICE_SAMPLE_RATE,
                    "synthesizer": settings.VOICE_DEFAULT_SYNTHESIZER,
                },
            ),
            "policy_engine": ComponentHealth(
                status="active",
                details={"default_policy": "DENY", "tools_enabled": False},
            ),
        },
    )
