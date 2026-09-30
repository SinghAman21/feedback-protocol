"""Shared data model for the eval framework."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Verdict = Literal["pass", "fail", "partial"]

# Criterion ids the evaluator knows how to check. rubric.yaml files mark
# each one as required or informational for their scenario.
CRITERION_IDS = (
    "task_understanding",
    "investigation_completeness",
    "factual_correctness",
    "evidence_quality",
    "correct_feedback_type",
    "false_positive_avoidance",
    "protocol_compliance",
    "privacy",
    "human_readability",
)


@dataclass(frozen=True)
class ExpectedFinding:
    type: str
    summary_keywords: tuple[str, ...] = ()
    capability: str | None = None
    endpoint: str | None = None
    required_evidence: tuple[str, ...] = ()
    forbidden_claims: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExpectedResult:
    findings: tuple[ExpectedFinding, ...] = ()
    expect_no_feedback: bool = False
    report_requirements: tuple[str, ...] = ()
    forbidden_report_claims: tuple[str, ...] = ()


@dataclass(frozen=True)
class RubricCriterion:
    id: str
    description: str
    required: bool
    applies_when: str | None = None


@dataclass(frozen=True)
class Rubric:
    criteria: tuple[RubricCriterion, ...]


@dataclass(frozen=True)
class EvalDefinition:
    """One fully loaded eval: metadata + task + ground truth + rubric."""

    name: str
    description: str
    version: str
    directory: Path
    task: str
    expected: ExpectedResult
    rubric: Rubric
    skill_path: Path


@dataclass(frozen=True)
class AgentResult:
    """Standard output contract for an eval execution.

    findings: protocol-compatible feedback objects (each should validate
    against schema/feedback.schema.json; extra fields are allowed).
    report_markdown: human-readable investigation report (# Feature Review...).
    """

    findings: tuple[dict, ...] = ()
    report_markdown: str = ""


@dataclass(frozen=True)
class CriterionResult:
    criterion_id: str
    description: str
    required: bool
    verdict: Verdict
    explanation: str
    confidence: float | None = None


@dataclass(frozen=True)
class FindingEvaluation:
    expected_type: str
    matched: bool
    verdict: Verdict
    missing_evidence: tuple[str, ...] = ()
    unexpected_claims: tuple[str, ...] = ()
    explanation: str = ""


@dataclass(frozen=True)
class EvalReport:
    eval_name: str
    passed: bool
    criteria: tuple[CriterionResult, ...] = ()
    findings: tuple[FindingEvaluation, ...] = ()
    agent_executed: bool = False

    def failed_required(self) -> tuple[CriterionResult, ...]:
        return tuple(c for c in self.criteria if c.required and c.verdict != "pass")


class AgentNotConfigured(Exception):
    """Raised when no agent runtime is connected."""


class AgentRunner(abc.ABC):
    """Abstraction for executing an agent against one eval.

    Concrete implementations connect a real model/agent runtime. They
    receive the task text, the fixture repository path, and the full
    SKILL.md text, and return the agent's machine + human output.
    """

    @abc.abstractmethod
    def run(self, *, task: str, repository: Path, skill: str) -> AgentResult:
        """Run the agent. Must not fabricate results."""
        raise NotImplementedError


class NullAgentRunner(AgentRunner):
    """Placeholder used when no agent runtime is configured."""

    def run(self, *, task: str, repository: Path, skill: str) -> AgentResult:
        raise AgentNotConfigured(
            "Agent execution not configured. "
            "Provide an AgentRunner implementation to execute evals."
        )
