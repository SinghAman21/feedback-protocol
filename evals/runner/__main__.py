"""CLI entry point: `python -m evals.runner [--eval NAME] [--list]`."""

from __future__ import annotations

import argparse
import sys

from evals.runner.loader import EVAL_NAMES, FIXTURES_DIR, discover_fixtures, validate_fixture
from evals.runner.models import NullAgentRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m evals.runner",
        description="Discover and validate Agent Feedback Skill evals.",
    )
    parser.add_argument("--eval", default=None, help="Run a single eval by name.")
    parser.add_argument("--list", action="store_true", help="List available evals.")
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

    # No agent runtime is connected yet: validate only, never fake results.
    _ = NullAgentRunner()
    print("\nAgent execution not configured.")
    print("Fixture validation succeeded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
