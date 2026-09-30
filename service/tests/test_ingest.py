"""Ingestion: protocol compliance, service identity, timestamps, scrubbing."""

from __future__ import annotations

import json

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
    assert rec["service"] == {
        "name": "users-api",
        "version": None,
        "environment": "production",
    }
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


def test_shared_schema_fixtures_ingest_cleanly(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    from pathlib import Path

    fixture_dir = Path(__file__).resolve().parent.parent.parent / "schema" / "examples"
    files = sorted(fixture_dir.glob("*.json"))
    assert len(files) >= 4
    for path in files:
        payload = json.loads(path.read_text())
        resp = client.post("/feedback", json=payload, headers=auth_headers)
        assert resp.status_code == 201, path.name
        assert resp.json()["status"] == "received"


def test_service_version_identity_preserved(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    payload = {
        "service": {"name": "payments-api", "version": "4.2.1", "environment": "production"},
        "type": "bug",
        "summary": "500 on charge",
    }
    fid = client.post("/feedback", json=payload, headers=auth_headers).json()["id"]
    rec = client.get(f"/feedback/{fid}", headers=auth_headers).json()
    assert rec["service"] == {
        "name": "payments-api",
        "version": "4.2.1",
        "environment": "production",
    }


def test_correlation_ids_preserved_end_to_end(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    payload = {
        "type": "bug",
        "summary": "500 with full correlation",
        "request_id": "req_123",
        "session_id": "sess_abc",
        "trace_id": "trace_001",
    }
    fid = client.post("/feedback", json=payload, headers=auth_headers).json()["id"]
    stored = client.get(f"/feedback/{fid}", headers=auth_headers).json()["feedback"]
    assert stored["request_id"] == "req_123"
    assert stored["session_id"] == "sess_abc"
    assert stored["trace_id"] == "trace_001"


def test_expected_object_form_preserved(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    payload = {
        "type": "missing_feature",
        "summary": "no pagination",
        "expected": {"capability": "pagination"},
    }
    fid = client.post("/feedback", json=payload, headers=auth_headers).json()["id"]
    stored = client.get(f"/feedback/{fid}", headers=auth_headers).json()["feedback"]
    assert stored["expected"] == {"capability": "pagination"}


def test_secrets_never_reach_the_database_file(
    client: TestClient, auth_headers: dict[str, str], tmp_path
) -> None:
    secret = "sk-live-NEVERSTORE123"
    payload = {
        "type": "bug",
        "summary": "login fails",
        "metadata": {"api_key": secret, "note": f"used {secret} twice"},
    }
    client.post("/feedback", json=payload, headers=auth_headers)
    db_files = list(tmp_path.glob("*.db"))
    assert db_files, "expected the test database file"
    raw = db_files[0].read_bytes()
    assert secret.encode() not in raw


def test_credential_shaped_values_scrubbed_on_ingest(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    payload = {
        "type": "bug",
        "summary": "auth wall blocks health check",
        "description": "Server replied Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.x.y",
        "observed": {"status": 500, "detail": "HTTP 500, request_id=req_123"},
    }
    fid = client.post("/feedback", json=payload, headers=auth_headers).json()["id"]
    stored = client.get(f"/feedback/{fid}", headers=auth_headers).json()["feedback"]
    assert "eyJhbGciOiJIUzI1NiJ9" not in stored["description"]
    assert stored["observed"]["detail"] == "HTTP 500, request_id=req_123"
