"""Tests for the storage abstraction and ID generation."""

from __future__ import annotations

import asyncio

import pytest

from feedback_protocol.ids import generate_feedback_id, is_feedback_id
from feedback_protocol.models import Feedback
from feedback_protocol.store import FeedbackStore, InMemoryFeedbackStore


def test_generate_feedback_id_format() -> None:
    fid = generate_feedback_id()
    assert fid.startswith("fb_")
    assert is_feedback_id(fid)
    assert not is_feedback_id("fb_123")
    assert not is_feedback_id("123")


def test_ids_unique() -> None:
    assert len({generate_feedback_id() for _ in range(1000)}) == 1000


async def _save(store: FeedbackStore, summary: str) -> str:
    record = await store.save(Feedback(type="bug", summary=summary))
    return record.id


def test_inmemory_save_get_count() -> None:
    async def run() -> None:
        store = InMemoryFeedbackStore()
        assert await store.count() == 0
        assert await store.get("fb_doesnotexist0000000000") is None
        fid = await _save(store, "hello")
        assert await store.count() == 1
        record = await store.get(fid)
        assert record is not None
        assert record.feedback.summary == "hello"
        assert record.received_at.tzinfo is not None

    asyncio.run(run())


def test_inmemory_list_pagination() -> None:
    async def run() -> None:
        store = InMemoryFeedbackStore()
        for i in range(5):
            await _save(store, f"report {i}")
        page1 = await store.list(limit=2, offset=0)
        page2 = await store.list(limit=2, offset=2)
        page3 = await store.list(limit=2, offset=4)
        assert [r.feedback.summary for r in page1] == ["report 0", "report 1"]
        assert [r.feedback.summary for r in page2] == ["report 2", "report 3"]
        assert [r.feedback.summary for r in page3] == ["report 4"]

    asyncio.run(run())


def test_custom_store_implementation_can_back_router() -> None:
    """A minimal custom store works without changing the HTTP protocol."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from feedback_protocol.fastapi import create_feedback_router
    from feedback_protocol.models import StoredFeedback

    class CountingStore(InMemoryFeedbackStore):
        def __init__(self) -> None:
            super().__init__()
            self.saves = 0

        async def save(self, feedback: Feedback) -> StoredFeedback:
            self.saves += 1
            return await super().save(feedback)

    store = CountingStore()
    app = FastAPI()
    app.include_router(create_feedback_router(store=store))
    client = TestClient(app)
    assert client.post("/feedback", json={"type": "bug", "summary": "x"}).status_code == 201
    assert store.saves == 1


def test_feedback_store_is_abstract() -> None:
    with pytest.raises(TypeError):
        FeedbackStore()  # type: ignore[abstract]
