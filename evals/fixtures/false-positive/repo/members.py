"""Team member removal (workspace service)."""

from __future__ import annotations

import json
import time

_MEMBERS = {f"m{i}": {"id": f"m{i}"} for i in range(5)}
_CALLS: list[float] = []

RATE_LIMIT_PER_MINUTE = 100


def remove_member(member_id: str) -> tuple[int, str]:
    """Remove exactly one member. Bulk removal is intentionally unsupported."""
    now = time.time()
    while _CALLS and _CALLS[0] < now - 60:
        _CALLS.pop(0)
    if len(_CALLS) >= RATE_LIMIT_PER_MINUTE:
        return 429, json.dumps({"error": "rate_limited", "retry_after_s": 60})
    _CALLS.append(now)
    if member_id in _MEMBERS:
        del _MEMBERS[member_id]
        return 200, json.dumps({"removed": member_id})
    return 404, json.dumps({"error": "not_found"})
