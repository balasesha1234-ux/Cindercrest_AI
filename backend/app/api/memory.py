"""REST API endpoints for inspecting, adding, correcting, and deleting memory items."""

import secrets
import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, status

from backend.app.core.exceptions import NotFoundError
from backend.app.core.security import verify_session_token
from backend.app.memory.retriever import memory_retriever
from backend.app.memory.schema import (
    CorrectMemoryRequest,
    CreateMemoryRequest,
    MemoryCategory,
    MemoryItem,
    MemoryStatus,
)
from backend.app.memory.store import memory_store

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


@router.get(
    "",
    response_model=list[MemoryItem],
    dependencies=[Depends(verify_session_token)],
)
async def list_memories(
    category: MemoryCategory | None = None,
    key: str | None = None,
    status_filter: MemoryStatus | None = MemoryStatus.ACTIVE,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[MemoryItem]:
    """List persistent memory items matching category and status filters."""
    return memory_store.list_memories(
        category=category, key=key, status=status_filter, limit=limit
    )


@router.post(
    "",
    response_model=MemoryItem,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_session_token)],
)
async def create_memory(payload: CreateMemoryRequest) -> MemoryItem:
    """Explicitly save a user preference, project state, or fact."""
    memory_id = f"mem_{int(time.time())}_{secrets.token_hex(4)}"
    now = datetime.now(UTC)

    item = MemoryItem(
        memory_id=memory_id,
        category=payload.category,
        key=payload.key,
        content=payload.content,
        confidence=payload.confidence,
        provenance=payload.provenance,
        status=MemoryStatus.ACTIVE,
        expires_at=payload.expires_at,
        created_at=now,
        updated_at=now,
    )
    return memory_store.save(item, privacy_mode=False)


@router.get(
    "/search",
    response_model=list[MemoryItem],
    dependencies=[Depends(verify_session_token)],
)
async def search_memories(
    query: str = Query(min_length=1, description="Semantic or keyword query"),
    limit: int = Query(default=10, ge=1, le=50),
) -> list[MemoryItem]:
    """Retrieve the most relevant memories for conversational context."""
    return memory_retriever.retrieve_context(query=query, limit=limit)


@router.get(
    "/{memory_id}",
    response_model=MemoryItem,
    dependencies=[Depends(verify_session_token)],
)
async def get_memory(memory_id: str) -> MemoryItem:
    """Retrieve a single memory item by ID."""
    item = memory_store.get(memory_id)
    if not item:
        raise NotFoundError(message=f"Memory '{memory_id}' was not found")
    return item


@router.put(
    "/{memory_id}",
    response_model=MemoryItem,
    dependencies=[Depends(verify_session_token)],
)
async def correct_memory(memory_id: str, payload: CorrectMemoryRequest) -> MemoryItem:
    """Correct an existing memory, creating a superseding chain."""
    return memory_store.correct(
        memory_id=memory_id,
        new_content=payload.content,
        provenance=payload.provenance,
        privacy_mode=False,
    )


@router.delete(
    "/{memory_id}",
    dependencies=[Depends(verify_session_token)],
)
async def delete_memory(memory_id: str, hard: bool = Query(default=False)) -> dict[str, bool]:
    """Delete a memory item so it is no longer used by the application."""
    success = memory_store.delete(memory_id, hard=hard)
    if not success:
        raise NotFoundError(message=f"Memory '{memory_id}' was not found")
    return {"deleted": True}
