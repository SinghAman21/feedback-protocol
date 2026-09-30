"""Ingestion: protocol compliance, service identity, timestamps, scrubbing."""

from __future__ import annotations

from fastapi.testclient import TestClient

from service.tests.conftest import CANONICAL


def test_valid_ingestion_returns_protocol_receipt(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    resp = client.post("/feedback", json=CANONICAL, headers=auth_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "received"
    assert body["id"].startswith("fb_")


def test_stored_record_preserves_evidence(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    fid = client.post("/feedback", json=CANONICAL, headers=auth_headers).json()["id"]
    rec = client.get(f"/feedback/{fid}", headers=auth_headers).json()
    assert rec["id"] == fid
    assert rec["status"] == "new"
    assert rec["service"] == {"name": "users-api", "environment": "production"}
    assert rec["feedback"]["type"] == "missing_feature"
    assert rec["feedback"]["goal"] == "Retrieve all users"
    assert rec["feedback"]["attempt"] == {"method": "GET", "path": "/api/v1/users"}
    assert rec["feedback"]["observed"]["item_count"] == 100000
    assert rec["feedback"]["missing_capability"] == "pagination"
    assert "received_at" in rec


def test_service_identity_string_form(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    payload = {"service": "payments-api", "type": "bug", "summary": "500 on charge"}
    fid = client.post("/feedback", json=payload, headers=auth_headers).json()["id"]
    rec = client.get(f"/feedback/{fid}", headers=auth_headers).json()
    assert rec["service"]["name"] == "payments-api"
    assert rec["service"]["environment"] is None


def test_service_identity_defaults_to_unknown(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    # Plain v0.1 body without `service` must still ingest (backward compat).
    payload = {"type": "bug", "summary": "500 on charge"}
    fid = client.post("/feedback", json=payload, headers=auth_headers).json()["id"]
    rec = client.get(f"/feedback/{fid}", headers=auth_headers).json()
    assert rec["service"]["name"] == "unknown"


def test_client_timestamp_preserved(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    payload = {**CANONICAL, "timestamp": "2026-01-15T12:34:56Z"}
    fid = client.post("/feedback", json=payload, headers=auth_headers).json()["id"]
    rec = client.get(f"/feedback/{fid}", headers=auth_headers).json()
    assert rec["feedback"]["timestamp"].startswith("2026-01-15T12:34:56")


def test_missing_timestamp_stamped_by_server(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    fid = client.post("/feedback", json=CANONICAL, headers=auth_headers).json()["id"]
    rec = client.get(f"/feedback/{fid}", headers=auth_headers).json()
    assert rec["feedback"]["timestamp"] is not None


def test_invalid_bodies_are_400(client: TestClient, auth_headers: dict[str, str]) -> None:
    cases = [
        {"type": "nope", "summary": "x"},  # unknown type
        {"type": "bug"},  # missing summary
        {"summary": "x"},  # missing type
        {},  # empty object
        {"type": "bug", "summary": ""},  # empty summary
        ["not", "an", "object"],  # array
    ]
    for payload in cases:
        resp = client.post("/feedback", json=payload, headers=auth_headers)
        assert resp.status_code == 400, payload


def test_malformed_and_empty_bodies_are_400(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    resp = client.post(
        "/feedback", content=b"{not json",
        headers={**auth_headers, "Content-Type": "application/json"},
    )
    assert resp.status_code == 400
    resp = client.post(
        "/feedback", content=b"",
        headers={**auth_headers, "Content-Type": "application/json"},
    )
    assert resp.status_code == 400


def test_secrets_are_scrubbed_before_storage(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    payload = {
        "service": "users-api",
        "type": "bug",
        "summary": "500 on login",
        "attempt": {
            "method": "POST",
            "path": "/api/v1/login",
            "headers": {"Authorization": "Bearer s3cr3t"},
        },
        "metadata": {
            "api_key": "sk-live-123",
            "nested": {"password": "hunter2"},
            "cookies": "session=abc",
            "safe": "keep-me",
        },
    }
    fid = client.post("/feedback", json=payload, headers=auth_headers).json()["id"]
    stored = client.get(f"/feedback/{fid}", headers=auth_headers).json()["feedback"]
    assert stored["attempt"]["headers"] == {"Authorization": "[redacted]"}
    assert stored["metadata"]["api_key"] == "[redacted]"
    assert stored["metadata"]["nested"] == {"password": "[redacted]"}
    assert stored["metadata"]["cookies"] == "[redacted]"
    assert stored["metadata"]["safe"] == "keep-me"


def test_unknown_fields_preserved_for_extensibility(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    payload = {"type": "bug", "summary": "x", "future_field": "must survive"}
    fid = client.post("/feedback", json=payload, headers=auth_headers).json()["id"]
    rec = client.get(f"/feedback/{fid}", headers=auth_headers).json()
    assert rec["feedback"]["future_field"] == "must survive"
