"""Text and JSON reporting for eval runs. Per-criterion, never one score."""

from __future__ import annotations

import json
from pathlib import Path

from evals.runner.models import EvalReport

_WIDTH = 24


def render_text(reports: list[EvalReport]) -> str:
    """Render the §12 summary format with failure details."""
    lines = ["Agent Feedback Evaluation", "=========================", ""]
    for report in reports:
        status = "PASS" if report.passed else "FAIL"
        lines.append(f"{report.eval_name:<{_WIDTH}} {status}")
    lines.append("")
    if not reports:
        lines.append("no scenarios evaluated")
        return "\n".join(lines) + "\n"
    for report in reports:
        if report.passed:
            continue
        lines.append(f"--- {report.eval_name} ---")
        for criterion in report.criteria:
            if criterion.required and criterion.verdict != "pass":
                lines.append(f"  criterion : {criterion.criterion_id} ({criterion.verdict})")
                lines.append(f"  expected  : {criterion.description}")
                lines.append(f"  actual    : {criterion.explanation}")
        for finding in report.findings:
            if finding.verdict != "pass":
                lines.append(f"  finding   : expected type {finding.expected_type} ({finding.verdict})")
                if finding.missing_evidence:
                    lines.append(f"  missing   : {list(finding.missing_evidence)}")
                if finding.unexpected_claims:
                    lines.append(f"  unexpected: {list(finding.unexpected_claims)}")
                lines.append(f"  detail    : {finding.explanation}")
        lines.append("")
    passed = sum(1 for r in reports if r.passed)
    lines.append(f"{passed}/{len(reports)} scenarios passed")
    return "\n".join(lines) + "\n"


def write_reports(reports: list[EvalReport], reports_dir: Path) -> Path:
    """Write summary.txt + per-eval JSON. Returns the summary path."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    summary_path = reports_dir / "summary.txt"
    summary_path.write_text(render_text(reports), encoding="utf-8")
    for report in reports:
        payload = {
            "eval_name": report.eval_name,
            "passed": report.passed,
            "agent_executed": report.agent_executed,
            "criteria": [
                {
                    "id": c.criterion_id,
                    "required": c.required,
                    "verdict": c.verdict,
                    "explanation": c.explanation,
                    "confidence": c.confidence,
                }
                for c in report.criteria
            ],
            "findings": [
                {
                    "expected_type": f.expected_type,
                    "matched": f.matched,
                    "verdict": f.verdict,
                    "missing_evidence": list(f.missing_evidence),
                    "unexpected_claims": list(f.unexpected_claims),
                    "explanation": f.explanation,
                }
                for f in report.findings
            ],
        }
        (reports_dir / f"{report.eval_name}.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )
    return summary_path
