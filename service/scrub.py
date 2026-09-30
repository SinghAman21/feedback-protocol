"""Secret redaction applied to every payload before persistence.

Any object key that looks like a credential (passwords, tokens, API keys,
authorization headers, cookies, sessions, …) has its value replaced with
``[redacted]``, recursively. Unknown future fields are therefore safe by
default: they can only leak if their key looks completely innocent.
"""

from __future__ import annotations

import re
from typing import Any

REDACTED = "[redacted]"

_SENSITIVE_KEY = re.compile(
    r"password|passwd|secret|token|api[_-]?key|access[_-]?key|"
    r"authorization|cookie|session|private[_-]?key|client[_-]?secret|"
    r"credentials|^auth$|set-cookie",
    re.IGNORECASE,
)


def is_sensitive_key(key: str) -> bool:
    return bool(_SENSITIVE_KEY.search(key))


def scrub(value: Any) -> Any:
    """Return a copy of ``value`` with sensitive entries redacted."""
    if isinstance(value, dict):
        return {
            k: REDACTED if is_sensitive_key(str(k)) else scrub(v)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [scrub(v) for v in value]
    return value
