"""Event listing behind GET /api/v1/events (audit trail service)."""

from __future__ import annotations

import json
import time

# Simulated production latency: the backing store scans the full audit log
# on every read, so each listing takes ~3s regardless of page size.
READ_LATENCY_S = 3


def _all_events() -> list[dict]:
    # Production holds ~100k audit events; the fixture synthesizes them.
    return [{"id": f"evt_{i}", "kind": "page_view"} for i in range(100_000)]


def handle_list_events(query: dict) -> tuple[int, str]:
    """Return one page of events. Pagination works; every call is slow."""
    time.sleep(READ_LATENCY_S)
    try:
        limit = int(query.get("limit", 50))
    except (TypeError, ValueError):
        limit = 50
    try:
        page = int(query.get("page", 1))
    except (TypeError, ValueError):
        page = 1
    limit = max(1, min(limit, 100))
    page = max(1, page)
    events = _all_events()
    start = (page - 1) * limit
    return 200, json.dumps(
        {"events": events[start : start + limit], "page": page, "limit": limit}
    )
