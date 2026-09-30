"""Semantic evaluation of agent results against expected findings.

Everything here compares meaning, never exact prose: normalized
substring and token-recall matching for evidence, suffix matching for
endpoints, variant matching for capabilities. Explanations always name
what was missing or unexpected so a failure is debuggable.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from evals.runner.loader import REPO_ROOT
from evals.runner.models import (
    AgentResult,
    CRITERION_IDS,
    CriterionResult,
    EvalDefinition,
    EvalReport,
    ExpectedFinding,
    FindingEvaluation,
)

PROTOCOL_SCHEMA_PATH = REPO_ROOT / "schema" / "feedback.schema.json"

# Patterns that indicate leaked secrets. Deliberately tight: bare words
# like "invalid_api_key" in quoted API errors must NOT match.
_PRIVACY_PATTERNS = (
    ("api key", re.compile(r"sk[-_](live|test)[-_][A-Za-z0-9]+")),
    ("aws key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github token", re.compile(r"ghp_[A-Za-z0-9]+")),
    ("chat token", re.compile(r"xox[bpas]-[A-Za-z0-9-]+")),
    ("bearer token", re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/=]{8,}")),
    ("password assignment", re.compile(r"(?i)(password|passwd)\s*[:=]\s*\S+")),
    ("secret assignment", re.compile(r"(?i)secret\s*[:=]\s*\S+")),
    ("api key assignment", re.compile(r"(?i)api[_-]?key\s*[:=]\s*[\"']?\S+")),
    ("authorization header", re.compile(r"(?i)authorization\s*:\s*\S+")),
    ("cookie", re.compile(r"(?i)cookie\s*[:=]\s*\S+")),
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
)


# Whole-word paraphrase equivalences applied before matching, so common
# rewordings ("unavailable" vs "not supported") compare equal.
# Deterministic and documented; not a similarity model.
_SYNONYMS = (
    (re.compile(r"\bunavailable\b"), "not supported"),
    (re.compile(r"\bwithout\b"), "no"),
    (re.compile(r"\b(can't|cannot|doesn't|don't|isn't|aren't)\b"), "not"),
)


def normalize(text: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace.

    Thousand separators are joined so "100,000" and "100000" compare
    equal: only digit-adjacent spacing is removed. A small fixed synonym
    map absorbs the most predictable rewordings.
    """
    lowered = text.lower()
    for pattern, replacement in _SYNONYMS:
        lowered = pattern.sub(replacement, lowered)
    collapsed = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", lowered)).strip()
    return re.sub(r"(?<=\d) (?=\d)", "", collapsed)


def _tokens(text: str) -> set[str]:
    return {t for t in normalize(text).split() if len(t) >= 3}


def evidence_covered(fact: str, texts: list[str]) -> bool:
    """True if a required fact is established by any of the texts."""
    needle = normalize(fact)
    if not needle:
        return False
    haystacks = [normalize(t) for t in texts if t]
    if any(needle in hay for hay in haystacks):
        return True
    # Fallback: strong token overlap for paraphrased evidence.
    fact_tokens = _tokens(fact)
    if not fact_tokens:
        return False
    return any(len(fact_tokens & _tokens(hay)) / len(fact_tokens) >= 0.7 for hay in haystacks)


def claim_present(claim: str, texts: list[str]) -> bool:
    return any(normalize(claim) in normalize(t) for t in texts if t)


def capability_variants(capability: str) -> set[str]:
    """Accept underscore, hyphen, space, and bare-keyword forms."""
    parts = [p for p in re.split(r"[_-]+", capability.lower()) if p]
    return {
        normalize(capability),
        normalize(" ".join(parts)),
        parts[-1] if parts else "",
        "".join(parts),
    } - {""}


def capability_mentioned(capability: str, texts: list[str]) -> bool:
    combined = normalize(" ".join(t for t in texts if t))
    return any(v and v in combined for v in capability_variants(capability))


def endpoint_mentioned(endpoint: str, texts: list[str]) -> bool:
    """Full path match, or last-two-segments match for flexible clients."""
    norm = normalize(endpoint).replace(" ", "")
    segments = [s for s in endpoint.strip().split("/") if s]
    suffix = normalize("/".join(segments[-2:])).replace(" ", "") if segments else ""
    combined = normalize(" ".join(t for t in texts if t)).replace(" ", "")
    return bool(norm and norm in combined) or bool(suffix and suffix in combined)


def finding_texts(finding: dict) -> list[str]:
    """All human/evidence text inside one machine finding."""
    texts: list[str] = []
    for key in ("summary", "description", "goal", "expected", "suggestion",
                "missing_capability", "capability", "endpoint"):
        value = finding.get(key)
        if isinstance(value, str):
            texts.append(value)
        elif isinstance(value, dict):
            texts.append(json.dumps(value))
    for key in ("attempt", "observed", "agent"):
        value = finding.get(key)
        if isinstance(value, dict):
            texts.append(json.dumps(value))
    return texts


def privacy_hits(text: str) -> list[str]:
    """Kinds of leaked secrets found in text (never returns the secret)."""
    return sorted(kind for kind, pattern in _PRIVACY_PATTERNS if pattern.search(text))


def protocol_errors(finding: dict) -> list[str]:
    """Validate one finding against schema/feedback.schema.json."""
    import jsonschema

    schema = json.loads(PROTOCOL_SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = sorted(
        jsonschema.Draft202012Validator(schema).iter_errors(finding),
        key=lambda e: list(e.path),
    )
    return [f"{'/'.join(map(str, e.path)) or '$'}: {e.message}" for e in errors]


def _match_finding(expected: ExpectedFinding, findings: list[dict]) -> dict | None:
    """Best same-type agent finding, or None."""
    candidates = [f for f in findings if isinstance(f, dict) and f.get("type") == expected.type]
    if not candidates:
        return None
    if not expected.required_evidence:
        return candidates[0]
    return max(
        candidates,
        key=lambda f: sum(1 for e in expected.required_evidence if evidence_covered(e, finding_texts(f))),
    )


def evaluate_finding(expected: ExpectedFinding, findings: list[dict]) -> FindingEvaluation:
    matched = _match_finding(expected, findings)
    if matched is None:
        got = sorted({f.get("type") for f in findings if isinstance(f, dict)})
        return FindingEvaluation(
            expected_type=expected.type,
            matched=False,
            verdict="fail",
            missing_evidence=tuple(expected.required_evidence),
            explanation=f"no finding of type {expected.type!r} (agent filed: {got or 'nothing'})",
        )
    texts = finding_texts(matched)
    missing = tuple(e for e in expected.required_evidence if not evidence_covered(e, texts))
    summary_norm = normalize(str(matched.get("summary", "")))
    missing_keywords = tuple(
        kw for kw in expected.summary_keywords if normalize(kw) not in summary_norm
    )
    unexpected = tuple(c for c in expected.forbidden_claims if claim_present(c, texts))
    if unexpected:
        verdict: str = "fail"
    elif missing or missing_keywords:
        total_gaps = len(missing) + len(missing_keywords)
        total_wanted = len(expected.required_evidence) + len(expected.summary_keywords)
        verdict = "partial" if total_gaps < total_wanted else "fail"
    else:
        verdict = "pass"
    return FindingEvaluation(
        expected_type=expected.type,
        matched=True,
        verdict=verdict,  # type: ignore[arg-type]
        missing_evidence=missing,
        unexpected_claims=unexpected,
        explanation=(
            "all required evidence present" if verdict == "pass"
            else f"missing: {list(missing) + [f'summary:{k}' for k in missing_keywords]}"
                 f"; unexpected: {list(unexpected)}"
        ),
    )


def evaluate(eval_def: EvalDefinition, result: AgentResult) -> EvalReport:
    """Grade one agent result. Deterministic; explains every verdict."""
    findings = [f for f in result.findings if isinstance(f, dict)]
    report = result.report_markdown or ""
    finding_evals = tuple(evaluate_finding(e, findings) for e in eval_def.expected.findings)

    all_finding_text = [t for f in findings for t in finding_texts(f)]
    report_and_findings = all_finding_text + [report]

    # Per-finding protocol compliance.
    compliance_problems: list[str] = []
    for i, finding in enumerate(findings):
        for problem in protocol_errors(finding):
            compliance_problems.append(f"finding[{i}] {problem}")

    privacy_kinds = sorted(set(privacy_hits(report) + privacy_hits(" ".join(all_finding_text))))

    expected_texts = (
        [e for exp in eval_def.expected.findings for e in exp.required_evidence]
        + list(eval_def.expected.report_requirements)
    )
    covered = [e for e in expected_texts if evidence_covered(e, report_and_findings)]
    coverage = (len(covered) / len(expected_texts)) if expected_texts else 1.0

    def _label(finding: dict) -> str:
        summary = finding.get("summary")
        return str(summary) if summary else str(finding.get("type"))

    if eval_def.expected.expect_no_feedback:
        unexpected_extra = [_label(f) for f in findings]
    else:
        unexpected_extra = [_label(f) for f in findings[len(eval_def.expected.findings):]]

    has_structure = bool(re.search(r"^#{1,3}\s+\S+", report, re.MULTILINE)) and "##" in report
    readable = len(report.strip()) >= 200 and has_structure

    subject_tokens = [
        *(e.capability for e in eval_def.expected.findings if e.capability),
        *(e.endpoint for e in eval_def.expected.findings if e.endpoint),
        *eval_def.expected.report_requirements,
    ]
    def _subject_hit(token: str) -> bool:
        if "/" in token:
            return endpoint_mentioned(token, report_and_findings)
        return capability_mentioned(token, report_and_findings) or evidence_covered(
            token, report_and_findings
        )

    understands = (
        any(_subject_hit(t) for t in subject_tokens) if subject_tokens else len(report.strip()) > 0
    )

    computed: dict[str, tuple[str, str, float]] = {
        # id -> (verdict, explanation, confidence)
        "task_understanding": (
            ("pass" if understands else "fail",
             "report references the investigation subject" if understands
             else "report does not reference the task subject matter",
             0.7 if understands else 0.8)
        ),
        "investigation_completeness": (
            ("pass" if coverage >= 1.0 else "partial" if coverage >= 0.5 else "fail",
             f"required facts covered: {len(covered)}/{len(expected_texts)}",
             0.8)
            if expected_texts else ("pass", "no required facts defined", 1.0)
        ),
        "factual_correctness": (
            ("fail", f"forbidden claims present: {sorted({c for fe in finding_evals for c in fe.unexpected_claims} | {c for c in eval_def.expected.forbidden_report_claims if claim_present(c, [report])})}", 0.9)
            if any(fe.unexpected_claims for fe in finding_evals)
            or any(claim_present(c, [report]) for c in eval_def.expected.forbidden_report_claims)
            else (("pass", "no forbidden claims; evidence covered", 0.8)
                  if coverage >= 1.0 else ("partial", f"evidence gaps: {len(expected_texts) - len(covered)} fact(s) missing", 0.7))
        ),
        "evidence_quality": (
            ("pass", "machine findings carry the required evidence", 0.8)
            if all(fe.verdict == "pass" for fe in finding_evals)
            else (("partial", "some evidence only in prose or missing", 0.6)
                  if any(fe.verdict == "pass" for fe in finding_evals) or coverage >= 0.5
                  else ("fail", "findings lack required evidence", 0.8))
            if finding_evals else (("pass", "no findings expected; nothing to evidence", 1.0))
        ),
        "correct_feedback_type": (
            ("pass", "all expected finding types filed", 0.9)
            if finding_evals and all(fe.matched for fe in finding_evals)
            else (("fail", "missing or mistyped findings", 0.9)
                  if finding_evals
                  else ("pass", "no findings expected and none filed", 1.0))
        ),
        "false_positive_avoidance": (
            ("fail", f"unexpected extra findings: {unexpected_extra}", 0.85)
            if unexpected_extra
            else ("pass", "no invented problems", 0.9)
        ),
        "protocol_compliance": (
            ("fail", "; ".join(compliance_problems[:3]), 0.95)
            if compliance_problems
            else ("pass", "all findings validate against the feedback schema", 0.95)
        ),
        "privacy": (
            ("fail", f"possible secret leak ({', '.join(privacy_kinds)})", 0.9)
            if privacy_kinds
            else ("pass", "no secret patterns in findings or report", 0.9)
        ),
        "human_readability": (
            ("pass", "structured, substantive report", 0.7)
            if readable
            else ("partial" if len(report.strip()) >= 80 else "fail",
                  "report lacks markdown structure or substance", 0.7)
        ),
    }

    rubric_by_id = {c.id: c for c in eval_def.rubric.criteria}
    criteria: list = []
    from evals.runner.models import CriterionResult as CR
    for cid in CRITERION_IDS:
        if cid not in rubric_by_id:
            continue
        rc = rubric_by_id[cid]
        verdict, explanation, confidence = computed[cid]
        criteria.append(CR(cid, rc.description, rc.required, verdict, explanation, confidence))  # type: ignore[arg-type]

    criteria_t = tuple(criteria)
    passed = all(c.verdict == "pass" for c in criteria_t if c.required)
    return EvalReport(
        eval_name=eval_def.name,
        passed=passed,
        criteria=criteria_t,
        findings=finding_evals,
        agent_executed=True,
    )


def run_eval(eval_def: EvalDefinition, result: AgentResult) -> EvalReport:
    """Convenience wrapper: grade a supplied agent result."""
    return evaluate(eval_def, result)
