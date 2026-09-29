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
