"""Event listing behind GET /api/v1/events (audit trail service)."""

from __future__ import annotations

import json


def _all_events() -> list[dict]:
    # Production holds ~100k audit events; the fixture synthesizes them.
    return [{"id": f"evt_{i}", "kind": "page_view"} for i in range(100_000)]


def handle_list_events(query: dict) -> tuple[int, str]:
    """Return every event in a single response. No pagination exists."""
    events = _all_events()
    return 200, json.dumps({"events": events})
