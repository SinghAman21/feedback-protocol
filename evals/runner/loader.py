"""Loading and structural validation of eval definitions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

EVALS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = EVALS_DIR.parent
FIXTURES_DIR = EVALS_DIR / "fixtures"
SCHEMA_DIR = EVALS_DIR / "schema"
SKILL_PATH = REPO_ROOT / "skill" / "SKILL.md"

EVAL_NAMES = (
    "feature-works",
    "missing-feature",
    "api-bug",
    "documentation-mismatch",
    "performance-problem",
    "missing-tests",
    "agent-mistake",
    "false-positive",
)


@dataclass(frozen=True)
class ValidationIssue:
    eval_name: str
    message: str


def _load_json(path: Path):
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def _validate_against_schema(instance, schema_path: Path, label: str) -> list[str]:
    import json

    import jsonschema

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = sorted(
        jsonschema.Draft202012Validator(schema).iter_errors(instance),
        key=lambda e: list(e.path),
    )
    return [f"{label}: {'/'.join(map(str, e.path)) or '$'}: {e.message}" for e in errors]


def validate_fixture(name: str, fixtures_dir: Path = FIXTURES_DIR) -> list[ValidationIssue]:
    """Validate one fixture's structure and files. Empty list = valid."""
    from evals.runner.models import CRITERION_IDS

    issues: list[ValidationIssue] = []

    def issue(message: str) -> None:
        issues.append(ValidationIssue(eval_name=name, message=message))

    directory = fixtures_dir / name
    if not directory.is_dir():
        return [ValidationIssue(eval_name=name, message="fixture directory missing")]

    meta_path = directory / "eval.json"
    if not meta_path.is_file():
        issue("eval.json missing")
    else:
        try:
            meta = _load_json(meta_path)
        except ValueError as exc:
            issue(f"eval.json is not valid JSON: {exc}")
            meta = None
        if meta is not None:
            for msg in _validate_against_schema(meta, SCHEMA_DIR / "eval.schema.json", "eval.json"):
                issue(msg)
            if meta.get("name") != name:
                issue(f"eval.json name {meta.get('name')!r} != directory {name!r}")

    task_path = directory / "task.md"
    if not task_path.is_file() or not task_path.read_text(encoding="utf-8").strip():
        issue("task.md missing or empty")

    expected_path = directory / "expected.json"
    if not expected_path.is_file():
        issue("expected.json missing")
    else:
        try:
            expected = _load_json(expected_path)
        except ValueError as exc:
            issue(f"expected.json is not valid JSON: {exc}")
            expected = None
        if expected is not None:
            for msg in _validate_against_schema(
                expected, SCHEMA_DIR / "expected-result.schema.json", "expected.json"
            ):
                issue(msg)

    rubric_path = directory / "rubric.yaml"
    if not rubric_path.is_file():
        issue("rubric.yaml missing")
    else:
        try:
            rubric = yaml.safe_load(rubric_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            issue(f"rubric.yaml is not valid YAML: {exc}")
            rubric = None
        if rubric is not None:
            if not isinstance(rubric, dict):
                issue("rubric.yaml must be a mapping")
            else:
                for msg in _validate_against_schema(
                    rubric, SCHEMA_DIR / "rubric.schema.json", "rubric.yaml"
                ):
                    issue(msg)
                seen = set()
                for criterion in (rubric.get("criteria") or []):
                    if isinstance(criterion, dict):
                        cid = criterion.get("id")
                        if cid in seen:
                            issue(f"rubric.yaml duplicates criterion {cid!r}")
                        seen.add(cid)
                        if cid not in CRITERION_IDS:
                            issue(f"rubric.yaml has unknown criterion {cid!r}")

    repo = directory / "repo"
    if not repo.is_dir():
        issue("repo/ directory missing")
    elif not any(repo.iterdir()):
        issue("repo/ directory is empty")

    return issues


def discover_fixtures(fixtures_dir: Path = FIXTURES_DIR) -> list[str]:
    """Return sorted fixture names present on disk."""
    if not fixtures_dir.is_dir():
        return []
    return sorted(p.name for p in fixtures_dir.iterdir() if p.is_dir())


def load_eval_definition(name: str, fixtures_dir: Path = FIXTURES_DIR):
    """Load a validated fixture into an EvalDefinition. Raises ValueError."""
    from evals.runner.models import (
        EvalDefinition,
        ExpectedFinding,
        ExpectedResult,
        Rubric,
        RubricCriterion,
    )

    issues = validate_fixture(name, fixtures_dir)
    if issues:
        raise ValueError("; ".join(i.message for i in issues))

    directory = fixtures_dir / name
    meta = _load_json(directory / "eval.json")
    expected_raw = _load_json(directory / "expected.json")
    rubric_raw = yaml.safe_load((directory / "rubric.yaml").read_text(encoding="utf-8"))

    findings = tuple(
        ExpectedFinding(
            type=f["type"],
            summary_keywords=tuple(f.get("summary_keywords", ())),
            capability=f.get("capability"),
            endpoint=f.get("endpoint"),
            required_evidence=tuple(f.get("required_evidence", ())),
            forbidden_claims=tuple(f.get("forbidden_claims", ())),
        )
        for f in expected_raw.get("findings", [])
    )
    expected = ExpectedResult(
        findings=findings,
        expect_no_feedback=bool(expected_raw.get("expect_no_feedback", False)),
        report_requirements=tuple(expected_raw.get("report_requirements", ())),
        forbidden_report_claims=tuple(expected_raw.get("forbidden_report_claims", ())),
    )
    rubric = Rubric(
        criteria=tuple(
            RubricCriterion(
                id=c["id"],
                description=c["description"],
                required=bool(c["required"]),
                applies_when=c.get("applies_when"),
            )
            for c in rubric_raw["criteria"]
        )
    )
    return EvalDefinition(
        name=name,
        description=meta["description"],
        version=meta["version"],
        directory=directory,
        task=(directory / meta.get("task_file", "task.md")).read_text(encoding="utf-8"),
        expected=expected,
        rubric=rubric,
        skill_path=SKILL_PATH,
    )
