# Eval runner

Minimal, provider-free runner for the Agent Feedback Skill evals.

## Interface

```bash
python -m evals.runner                 # discover + validate all evals
python -m evals.runner --eval missing-feature
python -m evals.runner --list
```

Today the runner discovers fixtures, validates `eval.json` / `task.md` /
`expected.json` / `rubric.yaml` / `repo/` against the schemas in
`evals/schema/`, and stops before agent execution:

```text
Agent execution not configured.
Fixture validation succeeded.
```

## Plugging in a real agent

Implement `AgentRunner` (`models.py`):

```python
from pathlib import Path
from evals.runner.models import AgentResult, AgentRunner

class MyAgentRunner(AgentRunner):
    def run(self, *, task: str, repository: Path, skill: str) -> AgentResult:
        # task: contents of task.md
        # repository: path to the fixture repo/ directory
        # skill: full text of skill/SKILL.md
        findings = [...]        # protocol-compatible feedback objects
        report = "# Feature Review\n..."
        return AgentResult(findings=tuple(findings), report_markdown=report)
```

Then grade the result:

```python
from evals.runner.evaluator import run_eval
from evals.runner.loader import load_eval_definition

definition = load_eval_definition("missing-feature")
report = run_eval(definition, MyAgentRunner().run(
    task=definition.task,
    repository=definition.directory / "repo",
    skill=definition.skill_path.read_text(),
))
```

`report.passed` is true only when every **required** rubric criterion is
a clean `pass`. The CLI writes the agent's raw output next to its fixture
(`agent-result.json` + `agent-report.md`) and prints the graded summary
with `reporters.render_text([report, ...])`.

## Modules

- `models.py` — dataclasses (`EvalDefinition`, `AgentResult`,
  `CriterionResult`, `EvalReport`), `AgentRunner` ABC, `NullAgentRunner`.
- `loader.py` — fixture discovery, structural + schema validation,
  `load_eval_definition`.
- `evaluator.py` — semantic comparison (normalized text, token recall,
  endpoint suffix matching), protocol-schema validation of findings,
  privacy scanning.
- `reporters.py` — text summary and JSON report writers.
