"""CLI entry point: `python -m evals.runner [--eval NAME] [--list] [--execute]`."""

from __future__ import annotations

import argparse
import importlib
import sys

from evals.runner.loader import (
    EVAL_NAMES,
    FIXTURES_DIR,
    discover_fixtures,
    load_eval_definition,
    validate_fixture,
)
from evals.runner.models import AgentRunner, NullAgentRunner, OpencodeAgentRunner


def _load_agent(dotted: str, *, model: str | None) -> AgentRunner:
    """Load AgentRunner from 'pkg.mod:Class' or 'pkg.mod.Class'."""
    name, _, cls_name = dotted.replace(":", ".").rpartition(".")
    if not name or not cls_name:
        raise ValueError(f"invalid --agent {dotted!r}, use 'pkg.mod:Class'")
    cls = getattr(importlib.import_module(name), cls_name)
    if isinstance(cls, type) and issubclass(cls, OpencodeAgentRunner):
        return cls(model=model)
    return cls()  # type: ignore[no-any-return]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m evals.runner",
        description="Discover, validate, and optionally execute Agent Feedback Skill evals.",
    )
    parser.add_argument("--eval", default=None, help="Run a single eval by name.")
    parser.add_argument("--list", action="store_true", help="List available evals.")
    parser.add_argument(
        "--execute",
        action="store_true",
        default=None,
        help="Execute agent and grade it (default: on with --eval, off without).",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate fixtures, never run the agent.",
    )
    parser.add_argument(
        "--agent",
        default=None,
        help="Custom runner 'pkg.mod:Class' (implies --execute).",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model for OpencodeAgentRunner (default: opencode default or OPENCODE_MODEL).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    names = discover_fixtures(FIXTURES_DIR)

    if args.list:
        for name in names:
            print(name)
        return 0

    selected = [args.eval] if args.eval else list(names)
    if args.eval and args.eval not in names:
        print(f"unknown eval: {args.eval} (available: {', '.join(names) or 'none'})")
        return 1

    all_issues = []
    for name in selected:
        all_issues.extend(validate_fixture(name, FIXTURES_DIR))
    for issue in all_issues:
        print(f"INVALID {issue.eval_name}: {issue.message}")

    missing = [n for n in EVAL_NAMES if n not in names] if not args.eval else []
    for name in missing:
        print(f"MISSING expected eval: {name}")

    if all_issues or missing:
        print(f"\n{len(selected)} eval(s) checked, {len(all_issues)} problem(s) found.")
        return 1

    if not args.eval:
        print(f"Discovered evals ({len(selected)}):")
        for name in selected:
            print(f"  - {name}")

    if args.agent:
        args.execute = True

    # `python -m evals.runner --eval NAME` executes by default.
    # Bare `python -m evals.runner` stays validate-only.
    if args.execute is None:
        args.execute = bool(args.eval) and not args.validate_only

    if args.validate_only or not args.execute:
        # No agent runtime requested: validate only, never fake results.
        _ = NullAgentRunner()
        print("\nAgent execution not configured.")
        print("Fixture validation succeeded.")
        print("Tip: `python -m evals.runner --eval NAME` runs OpencodeAgentRunner, or --agent pkg.mod:Class.")
        return 0

    from evals.runner.evaluator import run_eval
    from evals.runner.reporters import render_text

    import json

    agent: AgentRunner = (
        _load_agent(args.agent, model=args.model)
        if args.agent
        else OpencodeAgentRunner(model=args.model)
    )
    reports = []
    for name in selected:
        definition = load_eval_definition(name)
        result = agent.run(
            task=definition.task,
            repository=definition.directory / "repo",
            skill=definition.skill_path.read_text(encoding="utf-8"),
        )
        # Agent outputs live with their fixture; nothing goes elsewhere.
        (definition.directory / "agent-result.json").write_text(
            json.dumps(list(result.findings), indent=2), encoding="utf-8"
        )
        (definition.directory / "agent-report.md").write_text(
            result.report_markdown, encoding="utf-8"
        )
        reports.append(run_eval(definition, result))

    print(render_text(reports))
    return 0 if all(r.passed for r in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
