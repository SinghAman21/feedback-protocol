"""Model/schema parity: Python models must match the v0.1 JSON schema."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from feedback_protocol.models import Feedback, SUPPORTED_FEEDBACK_TYPES
from tests.conftest import CANONICAL_EXAMPLE

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema" / "feedback.schema.json"


def test_schema_required_fields_are_minimal() -> None:
    schema = json.loads(SCHEMA_PATH.read_text())
    assert schema["required"] == ["type", "summary"]
    assert set(schema["properties"]["type"]["enum"]) == set(SUPPORTED_FEEDBACK_TYPES)


def test_canonical_spec_example_validates_with_pydantic() -> None:
    feedback = Feedback.model_validate(CANONICAL_EXAMPLE)
    assert feedback.type == "missing_feature"
    assert feedback.attempt is not None and feedback.attempt.method == "GET"
    assert feedback.observed is not None and feedback.observed.status == 200


def test_canonical_spec_example_validates_with_jsonschema() -> None:
    jsonschema = pytest.importorskip("jsonschema")

    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.validate(instance=CANONICAL_EXAMPLE, schema=schema)


def test_model_rejects_unknown_type() -> None:
    with pytest.raises(ValidationError):
        Feedback.model_validate({"type": "nope", "summary": "x"})


def test_shared_fixtures_validate_with_pydantic_and_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")

    schema = json.loads(SCHEMA_PATH.read_text())
    fixture_dir = SCHEMA_PATH.parent / "examples"
    files = sorted(fixture_dir.glob("*.json"))
    assert len(files) >= 4, f"expected shared fixtures, got: {files}"
    for path in files:
        payload = json.loads(path.read_text())
        jsonschema.validate(instance=payload, schema=schema)
        Feedback.model_validate(payload)


def test_new_identity_and_evidence_fields() -> None:
    feedback = Feedback.model_validate(
        {
            "type": "bug",
            "summary": "x",
            "expected": {"capability": "pagination"},
            "service": {"name": "p", "version": "4.2.1", "environment": "prod"},
            "session_id": "sess_1",
            "trace_id": "trace_1",
        }
    )
    assert feedback.expected == {"capability": "pagination"}
    assert feedback.service is not None and feedback.service.name == "p"
    assert feedback.session_id == "sess_1"
    assert feedback.trace_id == "trace_1"

    as_name = Feedback.model_validate(
        {"type": "bug", "summary": "x", "service": "payments-api"}
    )
    assert as_name.service == "payments-api"

    # Old shapes still valid (backward compatibility).
    assert Feedback.model_validate(
        {"type": "bug", "summary": "x", "expected": "plain string"}
    ).expected == "plain string"

    for bad in [
        {"type": "bug", "summary": "x", "expected": ""},
        {"type": "bug", "summary": "x", "expected": 42},
        {"type": "bug", "summary": "x", "service": ""},
        {"type": "bug", "summary": "x", "service": 42},
        {"type": "bug", "summary": "x", "session_id": ""},
    ]:
        with pytest.raises(ValidationError):
            Feedback.model_validate(bad)
