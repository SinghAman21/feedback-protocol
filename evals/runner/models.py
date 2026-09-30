"""Shared data model for the eval framework."""

from __future__ import annotations

import abc
import json
import os
import re
import subprocess
from dataclasses import dataclass
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


class OpencodeAgentRunner(AgentRunner):
    """Real agent runner backed by the opencode CLI.

    Runs ``opencode run --format json`` with the fixture ``repo/`` as the
    working directory. The model only sees the task text, the skill text,
    and the repo — never ``expected.json`` / ``rubric.yaml`` (they live
    outside the working directory). Its output is parsed into an
    :class:`AgentResult` and graded by the evaluator. No fixture-specific
    logic, no hardcoded findings.

    Requires the ``opencode`` binary with an authenticated provider.
    Config via constructor or env: ``OPENCODE_MODEL``,
    ``OPENCODE_AGENT``, ``OPENCODE_RUN_TIMEOUT_S`` (default 600).
    """

    _FINDINGS_RE = re.compile(r"```json-findings\s*(.*?)```", re.DOTALL)
    _REPORT_RE = re.compile(r"```markdown-report\s*(.*?)```", re.DOTALL)

    def __init__(
        self,
        *,
        model: str | None = None,
        agent: str | None = None,
        timeout_s: float | None = None,
    ) -> None:
        self.model = model or os.environ.get("OPENCODE_MODEL") or None
        self.agent = agent or os.environ.get("OPENCODE_AGENT") or None
        self.timeout_s = (
            timeout_s
            if timeout_s is not None
            else float(os.environ.get("OPENCODE_RUN_TIMEOUT_S", "600"))
        )

    def run(self, *, task: str, repository: Path, skill: str) -> AgentResult:
        repository = Path(repository)
        prompt = self._build_prompt(task=task, skill=skill)
        cmd = ["opencode", "run", "--format", "json", "--dir", str(repository)]
        if self.model:
            cmd += ["--model", self.model]
        if self.agent:
            cmd += ["--agent", self.agent]
        try:
            proc = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "opencode binary not found on PATH; install opencode to run evals."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"opencode run timed out after {self.timeout_s}s for {repository}."
            ) from exc
        if proc.returncode != 0:
            raise RuntimeError(
                f"opencode run failed (exit {proc.returncode}): "
                f"{proc.stderr.strip()[-2000:]}"
            )
        text = self._collect_text(proc.stdout)
        return AgentResult(
            findings=self._parse_findings(text),
            report_markdown=self._parse_report(text),
        )

    def _build_prompt(self, *, task: str, skill: str) -> str:
        return (
            "You are an engineer investigating a codebase. "
            "Follow the Agent Feedback Skill below.\n\n"
            f"<skill>\n{skill}\n</skill>\n\n"
            f"<task>\n{task}\n</task>\n\n"
            "The task's repo is your current working directory. Investigate "
            "for real: list files, read the docs and implementation, run the "
            "test suite or repro commands. Do NOT modify any files; this is a "
            "read-only investigation. Do NOT read anything outside the "
            "working directory. Do NOT invent root causes; report only what "
            "you observed. NEVER include secrets, tokens, passwords, cookies, "
            "or Authorization headers in your output.\n\n"
            "When done, output EXACTLY two fenced blocks:\n\n"
            "```json-findings\n"
            "[ ... array of feedback objects, or [] when nothing is wrong ... ]\n"
            "```\n\n"
            "```markdown-report\n"
            "# ... human-readable investigation report ...\n"
            "```\n\n"
            "Rules:\n"
            '- json-findings: a JSON array. Each object MUST have "type" (one '
            "of bug, missing_feature, unexpected_behavior, documentation, "
            'performance) and "summary" (max 280 chars). Add "goal", '
            '"attempt", "observed", "expected", "missing_capability", '
            '"suggestion", "agent" where known.\n'
            '- markdown-report: start with a "# " title, use "## " sections '
            "(Goal, Findings, Evidence, Impact, Suggested next step), "
            "minimum 200 characters.\n"
            "Put the decisive facts (exact error strings, measured numbers, "
            "doc quotes, endpoint and capability names) inside the finding "
            "object's description/observed/expected fields, not only in the "
            "markdown report."
        )

    @staticmethod
    def _collect_text(payload: str) -> str:
        """Concatenate assistant text parts from `opencode run --format json`."""
        chunks: list[str] = []
        for line in payload.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            part = event.get("part")
            if (
                isinstance(part, dict)
                and part.get("type") == "text"
                and isinstance(part.get("text"), str)
            ):
                chunks.append(part["text"])
        return "\n".join(chunks)

    @classmethod
    def _parse_findings(cls, text: str) -> tuple[dict, ...]:
        match = cls._FINDINGS_RE.search(text)
        if not match:
            return ()
        try:
            raw = json.loads(match.group(1).strip())
        except ValueError:
            return ()
        if isinstance(raw, dict) and isinstance(raw.get("findings"), list):
            raw = raw["findings"]
        if not isinstance(raw, list):
            return ()
        return tuple(f for f in raw if isinstance(f, dict))

    @classmethod
    def _parse_report(cls, text: str) -> str:
        match = cls._REPORT_RE.search(text)
        if match:
            return match.group(1).strip()
        idx = text.find("# ")
        return text[idx:].strip() if idx != -1 else text.strip()
