"""Storage abstraction for received feedback.

No database is required. The default :class:`InMemoryFeedbackStore` keeps
records in process memory and is suitable for development and tests.

The :class:`FeedbackStore` interface is intentionally narrow (``save``,
``get``, ``list``, ``count``) and async, so future implementations backed
by PostgreSQL, Redis, or an external feedback service can be dropped in
without changing the HTTP protocol.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from feedback_protocol.models import Feedback, StoredFeedback
from feedback_protocol.ids import generate_feedback_id


class FeedbackStore(ABC):
    """Abstract persistence boundary for feedback records.

    Custom implementations MUST preserve the exact client-supplied
    :class:`Feedback` payload (v0.1 shape) alongside the server-assigned
    ``id`` and ``received_at`` timestamp.
    """

    @abstractmethod
    async def save(self, feedback: Feedback) -> StoredFeedback:
        """Assign an ID + receipt time, persist, and return the stored record."""
        raise NotImplementedError

    @abstractmethod
    async def get(self, feedback_id: str) -> StoredFeedback | None:
        """Return the record for ``feedback_id``, or ``None`` if unknown."""
        raise NotImplementedError

    @abstractmethod
    async def list(self, limit: int = 100, offset: int = 0) -> list[StoredFeedback]:
        """Return stored records in insertion order (paginated)."""
        raise NotImplementedError

    @abstractmethod
    async def count(self) -> int:
        """Return the total number of stored records."""
        raise NotImplementedError


class InMemoryFeedbackStore(FeedbackStore):
    """Non-persistent, in-process store for development and tests.

    Not suitable for multi-process production use: records live only in
    memory and are lost on restart. Use a database-backed
    :class:`FeedbackStore` for production.
    """

    def __init__(self) -> None:
        self._records: dict[str, StoredFeedback] = {}
        self._order: list[str] = []
        self._lock = asyncio.Lock()

    async def save(self, feedback: Feedback) -> StoredFeedback:
        received_at = datetime.now(timezone.utc)
        # Preserve a client-supplied timestamp; stamp receipt time separately.
        if feedback.timestamp is None:
            feedback = feedback.model_copy(update={"timestamp": received_at})
        record = StoredFeedback(
            id=generate_feedback_id(), received_at=received_at, feedback=feedback
        )
        async with self._lock:
            # Regenerate on the (astronomically unlikely) collision.
            while record.id in self._records:
                record = StoredFeedback(
                    id=generate_feedback_id(),
                    received_at=received_at,
                    feedback=feedback,
                )
            self._records[record.id] = record
            self._order.append(record.id)
        return record

    async def get(self, feedback_id: str) -> StoredFeedback | None:
        async with self._lock:
            return self._records.get(feedback_id)

    async def list(self, limit: int = 100, offset: int = 0) -> list[StoredFeedback]:
        async with self._lock:
            ids = self._order[offset : offset + limit]
            return [self._records[i] for i in ids]

    async def count(self) -> int:
        async with self._lock:
            return len(self._records)
