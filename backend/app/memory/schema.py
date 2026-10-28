"""Typed schemas for the Controlled Memory and Context system."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class MemoryCategory(StrEnum):
    """Authoritative memory classification categories."""

    CONVERSATION_CONTEXT = "conversation_context"
    PREFERENCE = "preference"
    PROJECT_STATE = "project_state"
    EXPLICIT_FACT = "explicit_fact"
    TEMPORARY_OBSERVATION = "temporary_observation"
    INFERENCE = "inference"


class MemoryStatus(StrEnum):
    """Lifecycle status of a stored memory item."""

    ACTIVE = "active"
    CORRECTED = "corrected"
    DELETED = "deleted"


class MemoryItem(BaseModel):
    """A discrete unit of remembered context with provenance and verification attributes."""

    memory_id: str = Field(description="Unique identifier e.g. mem_<timestamp>_<hex>")
    category: MemoryCategory = Field(description="Explicit category")
    key: str = Field(min_length=1, max_length=200, description="Semantic key or subject tag")
    content: str = Field(min_length=1, max_length=10000, description="Memory text content")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence level (1.0 for facts, 0.0-1.0 for inferences)"
    )
    provenance: str = Field(
        description="Origin of memory e.g. user_explicit, conversation:turn_3, task:task_123"
    )
    status: MemoryStatus = Field(default=MemoryStatus.ACTIVE)
    superseded_by: str | None = Field(
        default=None, description="Memory ID that superseded or corrected this item"
    )
    expires_at: datetime | None = Field(
        default=None, description="Expiration timestamp for temporary observations"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CreateMemoryRequest(BaseModel):
    """Request payload for storing a memory item."""

    category: MemoryCategory
    key: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=10000)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance: str = Field(default="user_explicit")
    expires_at: datetime | None = None


class CorrectMemoryRequest(BaseModel):
    """Request payload for correcting an existing memory item."""

    content: str = Field(min_length=1, max_length=10000)
    provenance: str = Field(default="user_correction")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
