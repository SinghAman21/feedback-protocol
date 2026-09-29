"""Shared pytest fixtures."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from feedback_protocol.fastapi import create_feedback_router
from feedback_protocol.store import InMemoryFeedbackStore


@pytest.fixture()
def store() -> InMemoryFeedbackStore:
    return InMemoryFeedbackStore()


@pytest.fixture()
def app(store: InMemoryFeedbackStore) -> FastAPI:
    application = FastAPI()
    application.include_router(create_feedback_router(store=store))
    return application


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


CANONICAL_EXAMPLE: dict = {
    "type": "missing_feature",
    "summary": "Users endpoint does not support pagination",
    "goal": "Retrieve all users",
    "attempt": {"method": "GET", "path": "/api/v1/users"},
    "observed": {"status": 200, "item_count": 100000},
    "missing_capability": "pagination",
    "suggestion": "Support cursor-based pagination",
    "agent": {"name": "example-agent", "version": "1.0.0"},
}
