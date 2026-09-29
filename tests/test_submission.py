"""Tests for POST /feedback: valid, invalid, types, timestamps, IDs."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from feedback_protocol.ids import is_feedback_id
from feedback_protocol.models import SUPPORTED_FEEDBACK_TYPES
from feedback_protocol.store import InMemoryFeedbackStore
from tests.conftest import CANONICAL_EXAMPLE


def test_valid_submission_returns_201_receipt(
    client: TestClient, store: InMemoryFeedbackStore
) -> None:
    resp = client.post("/feedback", json=CANONICAL_EXAMPLE)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "received"
    assert is_feedback_id(body["id"])
    # Persisted and retrievable from the store.
    import asyncio

    record = asyncio.run(store.get(body["id"]))
    assert record is not None
    assert record.feedback.summary == CANONICAL_EXAMPLE["summary"]


def test_minimal_submission_only_required_fields(client: TestClient) -> None:
    resp = client.post("/feedback", json={"type": "bug", "summary": "500 on documented call"})
    assert resp.status_code == 201
    assert resp.json()["status"] == "received"


@pytest.mark.parametrize("feedback_type", list(SUPPORTED_FEEDBACK_TYPES))
def test_all_supported_feedback_types(client: TestClient, feedback_type: str) -> None:
    resp = client.post(
        "/feedback", json={"type": feedback_type, "summary": f"summary for {feedback_type}"}
    )
    assert resp.status_code == 201, feedback_type
    assert is_feedback_id(resp.json()["id"])


def test_feedback_ids_are_unique(client: TestClient) -> None:
    ids = {
        client.post("/feedback", json={"type": "bug", "summary": f"report {i}"}).json()["id"]
        for i in range(25)
    }
    assert len(ids) == 25


def test_timestamp_absent_is_stamped_by_server(
    client: TestClient, store: InMemoryFeedbackStore
) -> None:
    import asyncio
    from datetime import datetime, timezone

    before = datetime.now(timezone.utc)
    feedback_id = client.post("/feedback", json={"type": "bug", "summary": "no ts"}).json()["id"]
    record = asyncio.run(store.get(feedback_id))
    assert record is not None
    assert record.feedback.timestamp is not None
    assert record.received_at >= before
    # Server stamps in UTC.
    assert record.received_at.tzinfo is not None


def test_timestamp_provided_is_preserved(
    client: TestClient, store: InMemoryFeedbackStore
) -> None:
    import asyncio

    resp = client.post(
        "/feedback",
        json={
            "type": "performance",
            "summary": "slow",
            "timestamp": "2026-01-15T12:34:56Z",
        },
    )
    assert resp.status_code == 201
    record = asyncio.run(store.get(resp.json()["id"]))
    assert record is not None
    assert record.feedback.timestamp is not None
    assert record.feedback.timestamp.isoformat().startswith("2026-01-15T12:34:56")


def test_invalid_type_is_400(client: TestClient) -> None:
    resp = client.post("/feedback", json={"type": "not_a_type", "summary": "x"})
    assert resp.status_code == 400
    assert "detail" in resp.json()


def test_missing_summary_is_400(client: TestClient) -> None:
    assert client.post("/feedback", json={"type": "bug"}).status_code == 400


def test_missing_type_is_400(client: TestClient) -> None:
    assert client.post("/feedback", json={"summary": "x"}).status_code == 400


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"type": "bug", "summary": ""},  # empty summary violates minLength 1
        {"type": "bug", "summary": "x" * 281},  # exceeds maxLength 280
        {"type": "bug", "summary": "x", "observed": {"status": 999}},
        {"type": "bug", "summary": "x", "agent": {"version": "1.0"}},  # name required
    ],
    ids=["empty-object", "empty-summary", "summary-too-long", "bad-status", "agent-no-name"],
)
def test_invalid_payloads_are_400(client: TestClient, payload: dict) -> None:
    assert client.post("/feedback", json=payload).status_code == 400


def test_empty_body_is_400(client: TestClient) -> None:
    resp = client.post("/feedback", content=b"", headers={"Content-Type": "application/json"})
    assert resp.status_code == 400


def test_malformed_json_is_400(client: TestClient) -> None:
    resp = client.post(
        "/feedback", content=b"{not json", headers={"Content-Type": "application/json"}
    )
    assert resp.status_code == 400


def test_json_array_is_400(client: TestClient) -> None:
    assert client.post("/feedback", json=["not", "an", "object"]).status_code == 400


def test_unknown_fields_are_accepted_for_extensibility(client: TestClient) -> None:
    # SPEC 7: unknown fields MUST be ignored, not rejected.
    resp = client.post(
        "/feedback",
        json={"type": "bug", "summary": "x", "future_field": "must not break v0.1"},
    )
    assert resp.status_code == 201
