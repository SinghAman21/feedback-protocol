"""Feedback ID generation.

IDs are opaque server-assigned strings of the form ``fb_<24 hex chars>``
(e.g. ``fb_9f3c2a1b4d5e6f708192a3b4``), using ``secrets`` for
unpredictability. The format is server-defined per SPEC 3.4 — clients MUST
treat IDs as opaque.
"""

from __future__ import annotations

import re
import secrets

ID_PREFIX = "fb_"
_ID_RE = re.compile(r"^fb_[0-9a-f]{24}$")


def generate_feedback_id() -> str:
    """Generate a new unique feedback ID."""
    return f"{ID_PREFIX}{secrets.token_hex(12)}"


def is_feedback_id(value: str) -> bool:
    """Return True if ``value`` looks like a generated feedback ID."""
    return bool(_ID_RE.match(value))
