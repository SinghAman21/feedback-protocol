"""Shared fixtures for the central-service tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from service.app import create_app

TEST_KEY = "test-key-123"


@pytest.fixture()
def client(tmp_path):
    app = create_app(db_path=str(tmp_path / "test.db"), api_key=TEST_KEY)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_KEY}"}


CANONICAL = {
    "service": {"name": "users-api", "environment": "production"},
    "type": "missing_feature",
    "summary": "Users endpoint does not support pagination",
    "goal": "Retrieve all users",
    "attempt": {"method": "GET", "path": "/api/v1/users"},
    "observed": {"status": 200, "item_count": 100000},
    "missing_capability": "pagination",
    "suggestion": "Support cursor-based pagination",
    "agent": {"name": "example-agent", "version": "1.0.0"},
}


def submit(client: TestClient, headers: dict[str, str], payload: dict) -> str:
    resp = client.post("/feedback", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]
