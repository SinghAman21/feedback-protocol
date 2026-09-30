"""Deterministic, explainable feedback grouping (no embeddings, no LLM).

Two reports land in the same cluster when they agree on every grouping
signal:

    (service name, feedback type, HTTP method, endpoint path,
     missing_capability)

The cluster ID is a hash of that key, so it is stable across restarts
and recomputations. Each cluster carries its grouping key back in the
response, so anyone can see exactly *why* these reports were grouped.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any

GroupKey = tuple[str, str, str, str, str]


def normalize_summary(summary: str) -> str:
    """Normalize free text for comparison: lowercase, de-accent, strip
    punctuation, collapse whitespace."""
    text = unicodedata.normalize("NFKD", summary).encode("ascii", "ignore").decode()
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def group_key_for(row: dict[str, Any]) -> GroupKey:
    """Build the grouping key for a stored row (flat dict from the DB)."""
    return (
        row.get("service_name") or "unknown",
        row.get("type") or "",
        row.get("method") or "",
        row.get("path") or "",
        row.get("missing_capability") or "",
    )


def cluster_id_for(key: GroupKey) -> str:
    """Deterministic cluster ID derived from the grouping key."""
    canonical = json.dumps(list(key), separators=(",", ":"), sort_keys=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
    return f"cluster_{digest}"
