# Agent Feedback Skill — Evaluations

These are **agent behavior evaluations**, not API unit tests.

The central question is:

> Can an agent, given a feature investigation task and the Agent Feedback
> Skill, discover real gaps and communicate them as useful structured
> feedback?

They are NOT designed primarily to answer:

> "Does POST /feedback return HTTP 200?"

That belongs in the normal test suite.

## What these evals test

Three different layers exist in this repository, and each has its own
tests:

- **Protocol tests** (`tests/`, `service/tests/`) verify the protocol:
  discovery, validation, status codes, storage, clustering, triage.
- **SDK tests** (`src/`, `node/`) verify implementations behave the same
  way in every language.
- **Evals** (`evals/`) verify **agent behavior**: both the
  machine-readable protocol output an agent produces *and* the
  human-readable quality of its investigation.

An eval passes only if the agent finds the right facts, files the right
kind of feedback (or correctly files nothing), backs claims with
evidence, and leaks no secrets.

## How an eval works

```text
fixture repository
  → task
  → Agent + skill/SKILL.md
  → investigation
  → structured feedback (agent-result.json)
  → human-readable report (agent-report.md)
  → evaluator
  → expected findings / rubric
```

Each fixture in `fixtures/` is a small self-contained repository with a
hidden property (a missing feature, a bug, a docs mismatch, … — or
nothing wrong at all). `task.md` gives the agent a goal without revealing
the answer. `expected.json` states the semantic ground truth as facts,
never exact prose. `rubric.yaml` lists the criteria a result is graded
against (`pass` / `fail` / `partial` per criterion, never one opaque
number).

The evaluator compares **meaning, not wording**: if the expected finding
is `missing_feature` / `csv_export` on `/customers/export`, an agent
report saying "The API does not currently provide CSV export for POST
/customers/export" passes.

## Running evals

```bash
python -m evals.runner            # discover + validate all evals
python -m evals.runner --eval missing-feature
python -m evals.runner --list
```

No model provider is required to run discovery and validation. Agent
execution is injected through the `AgentRunner` abstraction
(`evals/runner/models.py`); with no runtime configured the runner
validates every fixture and reports:

```text
Agent execution not configured.
Fixture validation succeeded.
```

## Layout

```text
evals/
├── README.md            # this file
├── schema/              # JSON schemas for eval definitions
├── runner/              # loader, evaluator, reporters, CLI
├── fixtures/            # 8 scenarios (repo + task + expected + rubric,
│                         # plus agent-result.json + agent-report.md after a run)
└── tests/               # tests for the eval framework itself
```
