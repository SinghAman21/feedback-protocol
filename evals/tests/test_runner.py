"""Tests for the eval framework itself (loader, evaluator, reporters).

These use synthetic agent results — no model provider needed — and prove
the evaluator grades meaning: good paraphrased results pass, wrong types,
missing evidence, extra findings, leaked secrets, and invalid protocol
output fail with explanations.
"""

from __future__ import annotations

from evals.runner import evaluator
from evals.runner.evaluator import (
    capability_mentioned,
    endpoint_mentioned,
    evaluate,
    evidence_covered,
    normalize,
    privacy_hits,
)
from evals.runner.loader import EVAL_NAMES, discover_fixtures, load_eval_definition, validate_fixture
from evals.runner.models import AgentNotConfigured, AgentResult, NullAgentRunner
from evals.runner.reporters import render_text


def _good_missing_feature() -> AgentResult:
    return AgentResult(
        findings=(
            {
                "type": "missing_feature",
                "summary": "The API does not currently provide CSV export for GET /api/v1/subscribers/export",
                "goal": "Export subscriber data as CSV for marketing",
                "attempt": {"method": "GET", "path": "/api/v1/subscribers/export"},
                "observed": {"status": 400, "error": "unsupported export format"},
                "expected": "a CSV download per the marketing workflow",
                "description": "JSON export is supported today; only json is listed.",
                "missing_capability": "csv_export",
                "suggestion": "Accept format=csv",
                "agent": {"name": "eval-agent", "version": "0.1"},
            },
        ),
        report_markdown=(
            "# Feature Review\n\n## Goal\nExport subscribers as CSV.\n\n"
            "## Findings\n### Missing capability\nCSV export is not supported; "
            "only JSON export is supported today.\n\n## Evidence\n"
            "GET /api/v1/subscribers/export?format=csv returns 400 "
            "unsupported export format; the code lists only json.\n\n"
            "## Impact\nMarketing copies JSON by hand.\n\n"
            "## Suggested next step\nAdd format=csv to the exporter.\n"
        ),
    )


def test_all_expected_evals_present_and_valid() -> None:
    assert set(discover_fixtures()) == set(EVAL_NAMES)
    for name in EVAL_NAMES:
        assert validate_fixture(name) == [], name


def test_each_fixture_loads() -> None:
    for name in EVAL_NAMES:
        definition = load_eval_definition(name)
        assert definition.name == name
        assert definition.task.strip()
        assert definition.skill_path.is_file()


def test_good_agent_passes_missing_feature() -> None:
    definition = load_eval_definition("missing-feature")
    report = evaluate(definition, _good_missing_feature())
    assert report.passed, [ (c.criterion_id, c.verdict, c.explanation) for c in report.criteria ]


def test_good_agent_passes_feature_works_with_no_findings() -> None:
    definition = load_eval_definition("feature-works")
    result = AgentResult(
        findings=(),
        report_markdown=(
            "# Feature Review\n\n## Goal\nCheck the documented export.\n\n"
            "## Findings\nNo problems found: JSON export works and matches "
            "the documented behavior. I ran the test suite; all tests pass.\n\n"
            "## Evidence\nledger.py implements export(json); api.md documents "
            "only json; test_ledger.py covers round-trip, empty, and bad format.\n\n"
            "## Impact\nNone — the feature is reliable.\n\n"
            "## Suggested next step\nNo action needed.\n"
        ),
    )
    report = evaluate(definition, result)
    assert report.passed, [(c.criterion_id, c.verdict, c.explanation) for c in report.criteria]


def test_wrong_feedback_type_fails() -> None:
    definition = load_eval_definition("missing-feature")
    good = _good_missing_feature()
    bad_finding = dict(good.findings[0])
    bad_finding["type"] = "bug"
    report = evaluate(definition, AgentResult((bad_finding,), good.report_markdown))
    assert not report.passed
    by_id = {c.criterion_id: c for c in report.criteria}
    assert by_id["correct_feedback_type"].verdict == "fail"


def test_missing_evidence_downgrades() -> None:
    definition = load_eval_definition("missing-feature")
    thin = {
        "type": "missing_feature",
        "summary": "CSV export missing",
        "missing_capability": "csv_export",
    }
    report = evaluate(
        definition,
        AgentResult((thin,), "# Feature Review\n\n## Goal\nCSV.\n\n## Findings\nNone.\n\n## Evidence\nNone.\n\n## Impact\nNone.\n\n## Suggested next step\nNone.\n" + "x" * 200),
    )
    assert not report.passed
    by_id = {c.criterion_id: c for c in report.criteria}
    assert by_id["evidence_quality"].verdict in ("fail", "partial")


def test_extra_finding_fails_false_positive_avoidance() -> None:
    definition = load_eval_definition("feature-works")
    extra = {
        "type": "bug",
        "summary": "Export might be slow with big data",
        "goal": "Export customers",
    }
    result = AgentResult(
        (extra,),
        "# Feature Review\n\n## Goal\nExport.\n\n## Findings\nMaybe slow.\n\n"
        "## Evidence\nGuessed.\n\n## Impact\nUnknown.\n\n## Suggested next step\nNone.\n" + "y" * 200,
    )
    report = evaluate(definition, result)
    assert not report.passed
    by_id = {c.criterion_id: c for c in report.criteria}
    assert by_id["false_positive_avoidance"].verdict == "fail"


def test_leaked_secret_fails_privacy() -> None:
    definition = load_eval_definition("feature-works")
    leaked = (
        "# Feature Review\n\n## Goal\nExport.\n\n## Findings\nWorks.\n\n## Evidence\n"
        "Used key sk_test_FAKE000000000000000000 from settings.\n\n"
        "## Impact\nNone.\n\n## Suggested next step\nNone.\n" + "z" * 200
    )
    report = evaluate(definition, AgentResult((), leaked))
    assert not report.passed
    by_id = {c.criterion_id: c for c in report.criteria}
    assert by_id["privacy"].verdict == "fail"


def test_invalid_protocol_finding_fails_compliance() -> None:
    definition = load_eval_definition("missing-feature")
    invalid = {"type": "missing_feature"}  # summary missing
    result = AgentResult(
        (invalid,),
        _good_missing_feature().report_markdown,
    )
    report = evaluate(definition, result)
    by_id = {c.criterion_id: c for c in report.criteria}
    assert by_id["protocol_compliance"].verdict == "fail"


def test_forbidden_claim_fails_factual_correctness() -> None:
    definition = load_eval_definition("missing-feature")
    good = _good_missing_feature()
    finding = dict(good.findings[0])
    finding["description"] = "This database bug corrupts exports."
    report = evaluate(definition, AgentResult((finding,), good.report_markdown))
    assert not report.passed
    assert any(c.criterion_id == "factual_correctness" and c.verdict == "fail" for c in report.criteria)


def test_semantic_helpers() -> None:
    assert normalize("GET /api/v1/x!  ") == "get api v1 x"
    assert normalize("100,000 records") == "100000 records"
    assert evidence_covered("CSV export is not supported", ["csv export is not supported today"])
    assert evidence_covered("returns 500", ["The endpoint returns HTTP 500 for valid ids"])
    assert not evidence_covered("returns 500", ["everything works fine"])
    assert capability_mentioned("csv_export", ["No CSV export available"])
    assert endpoint_mentioned("/api/v1/subscribers/export", ["tried /subscribers/export path"])
    assert endpoint_mentioned("/api/v1/invoices", ["GET /api/v1/invoices/inv_2 failed"])
    assert not endpoint_mentioned("/api/v1/invoices", ["unrelated text here"])
    assert privacy_hits('key is "sk_test_FAKE123"') != []
    assert privacy_hits('{"error": "invalid_api_key"}') == []
    assert privacy_hits("normal report text") == []


def test_report_rendering_marks_failures() -> None:
    definition = load_eval_definition("missing-feature")
    report = evaluate(definition, AgentResult((), "too short"))
    text = render_text([report])
    assert "missing-feature" in text and "FAIL" in text
    assert "0/1 scenarios passed" in text
    assert "criterion" in text


def test_null_runner_raises_without_faking() -> None:
    import pytest

    runner = NullAgentRunner()
    with pytest.raises(AgentNotConfigured):
        runner.run(task="t", repository="/tmp", skill="s")  # type: ignore[arg-type]
