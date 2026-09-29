"""Tests for GET /.well-known/feedback-protocol."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from feedback_protocol.fastapi import DISCOVERY_PATH, create_feedback_router
from feedback_protocol.models import PROTOCOL_VERSION
from tests.conftest import CANONICAL_EXAMPLE  # noqa: F401 (shared fixture import)


def test_discovery_canonical_path(client: TestClient) -> None:
    resp = client.get(DISCOVERY_PATH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == PROTOCOL_VERSION == "0.1"
    assert body["feedback_endpoint"] == "/feedback"
    assert body["methods"] == ["POST"]


def test_discovery_advertises_custom_feedback_path() -> None:
    from feedback_protocol.store import InMemoryFeedbackStore

    app = FastAPI()
    app.include_router(
        create_feedback_router(store=InMemoryFeedbackStore(), feedback_path="/api/feedback")
    )
    client = TestClient(app)
    assert client.get(DISCOVERY_PATH).json()["feedback_endpoint"] == "/api/feedback"
    # Submission works at the advertised path.
    resp = client.post("/api/feedback", json={"type": "bug", "summary": "x"})
    assert resp.status_code == 201


def test_discovery_unknown_path_is_404(client: TestClient) -> None:
    assert client.get("/.well-known/does-not-exist").status_code == 404
