"""Unit tests for secret redaction (pure function, no HTTP)."""

from __future__ import annotations

from service.scrub import REDACTED, scrub


def test_sensitive_keys_redacted_recursively() -> None:
    payload = {
        "password": "hunter2",
        "nested": {"api_key": "sk-live-1", "deep": {"cookie": "s=1"}},
        "items": [{"token": "t"}, "plain"],
    }
    out = scrub(payload)
    assert out["password"] == REDACTED
    assert out["nested"]["api_key"] == REDACTED
    assert out["nested"]["deep"] == {"cookie": REDACTED}
    assert out["items"] == [{"token": REDACTED}, "plain"]


def test_authorization_and_session_keys() -> None:
    out = scrub(
        {
            "Authorization": "Bearer abc",
            "headers": {"Cookie": "s=1", "Content-Type": "application/json"},
            "session_token": "sess-secret",
            # Protocol correlation IDs are evidence, not secrets.
            "session_id": "sess_abc",
            "request_id": "req_123",
        }
    )
    assert out["Authorization"] == REDACTED
    assert out["headers"] == {"Cookie": REDACTED, "Content-Type": "application/json"}
    assert out["session_token"] == REDACTED
    assert out["session_id"] == "sess_abc"
    assert out["request_id"] == "req_123"


def test_credential_shaped_values_under_innocent_keys() -> None:
    out = scrub(
        {
            "note": "tried Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig",
            "key": "sk-live-4eC39HqLyjWDarjtT1zdp7dc",
            "auth": "Basic dXNlcjpwYXNz",
            "pem": "-----BEGIN RSA PRIVATE KEY-----\nMIIB\n-----END RSA PRIVATE KEY-----",
        }
    )
    assert "eyJhbGciOiJIUzI1NiJ9" not in out["note"]
    assert "sk-live-4eC39HqLyjWDarjtT1zdp7dc" not in out["key"]
    assert "dXNlcjpwYXNz" not in out["auth"]
    assert "MIIB" not in out["pem"]


def test_useful_evidence_preserved() -> None:
    out = scrub(
        {
            "summary": "POST /api/v1/login returns HTTP 500",
            "observed": {"status": 500, "error": "internal_error"},
            "request_id": "req_123",
            "detail": "request_id=req_123 after 3 retries",
        }
    )
    assert out["summary"] == "POST /api/v1/login returns HTTP 500"
    assert out["observed"] == {"status": 500, "error": "internal_error"}
    assert out["request_id"] == "req_123"
    assert out["detail"] == "request_id=req_123 after 3 retries"


def test_non_string_leaves_untouched() -> None:
    assert scrub({"n": 42, "b": True, "z": None}) == {"n": 42, "b": True, "z": None}
