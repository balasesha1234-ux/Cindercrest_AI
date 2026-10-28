"""Relevance-scored memory retrieval engine formatting clear provenance and inference tags."""

import re

from backend.app.memory.schema import MemoryCategory, MemoryItem
from backend.app.memory.store import MemoryStore, memory_store

STOP_WORDS = {
    "a",
    "an",
    "the",
    "is",
    "are",
    "was",
    "were",
    "what",
    "where",
    "when",
    "who",
    "how",
    "my",
    "your",
    "me",
    "you",
    "tell",
    "about",
    "does",
    "do",
    "for",
    "in",
    "on",
    "at",
    "of",
    "to",
}

CATEGORY_WEIGHTS: dict[MemoryCategory, float] = {
    MemoryCategory.EXPLICIT_FACT: 1.3,
    MemoryCategory.PREFERENCE: 1.3,
    MemoryCategory.PROJECT_STATE: 1.1,
    MemoryCategory.INFERENCE: 0.8,
    MemoryCategory.TEMPORARY_OBSERVATION: 0.7,
    MemoryCategory.CONVERSATION_CONTEXT: 0.6,
}

TAG_HEADERS: dict[MemoryCategory, str] = {
    MemoryCategory.EXPLICIT_FACT: "[REMEMBERED FACT]",
    MemoryCategory.PREFERENCE: "[USER PREFERENCE]",
    MemoryCategory.PROJECT_STATE: "[PROJECT STATE]",
    MemoryCategory.TEMPORARY_OBSERVATION: "[TEMPORARY OBSERVATION]",
    MemoryCategory.CONVERSATION_CONTEXT: "[CONVERSATION CONTEXT]",
}


class MemoryRetriever:
    """Retrieves and formats strictly relevant context memories while respecting Privacy Mode."""

    def __init__(self, store: MemoryStore | None = None) -> None:
        self.store = store or memory_store

    def retrieve_context(
        self,
        query: str,
        privacy_mode: bool = False,
        limit: int = 5,
        min_confidence: float = 0.5,
    ) -> list[MemoryItem]:
        """Retrieve the most relevant memories for the query string."""
        if privacy_mode:
            return []

        # Purge expired items before querying
        self.store.purge_expired()

        active_items = self.store.list_memories(limit=200)
        if not active_items:
            return []

        # Tokenize query
        tokens = [
            t
            for t in re.findall(r"\b[a-zA-Z0-9_\-]{2,}\b", query.lower())
            if t not in STOP_WORDS
        ]
        if not tokens:
            return active_items[:limit]

        scored: list[tuple[float, MemoryItem]] = []

        for item in active_items:
            if item.confidence < min_confidence:
                continue

            key_lower = item.key.lower()
            content_lower = item.content.lower()

            base_score = 0.0
            for t in tokens:
                if t in key_lower:
                    base_score += 4.0
                if t in content_lower:
                    base_score += 1.5

            if base_score <= 0.0:
                continue

            multiplier = CATEGORY_WEIGHTS.get(item.category, 1.0)
            if item.category == MemoryCategory.INFERENCE:
                multiplier *= item.confidence

            final_score = base_score * multiplier
            scored.append((final_score, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:limit]]

    def format_context_for_prompt(
        self,
        query: str,
        privacy_mode: bool = False,
        limit: int = 5,
    ) -> str:
        """Format retrieved memories with explicit provenance and inference demarcation tags."""
        items = self.retrieve_context(query, privacy_mode=privacy_mode, limit=limit)
        if not items:
            return ""

        formatted_lines = []
        for item in items:
            if item.category == MemoryCategory.INFERENCE:
                tag = f"[INFERENCE (confidence: {item.confidence:.1f})]"
            else:
                tag = TAG_HEADERS.get(item.category, "[REMEMBERED ITEM]")

            formatted_lines.append(f"{tag} {item.key}: {item.content} (Source: {item.provenance})")

        return "\n".join(formatted_lines)


memory_retriever = MemoryRetriever()
