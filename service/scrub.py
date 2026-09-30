"""Secret redaction applied to every payload BEFORE persistence.

Ingestion flow is always: request → validation → scrubbing → persistence.
Nothing raw is ever stored: only the scrubbed copy reaches the database.

Two layers:

1. Sensitive KEYS (passwords, tokens, API keys, authorization headers,
   cookies, sessions, …) have their values replaced with ``[redacted]``,
   recursively. Unknown future fields are therefore safe by default.
2. Sensitive VALUE patterns inside otherwise innocent strings: bearer /
   basic credentials, ``sk-live`` / ``sk-test`` style keys, and PEM
   private-key blocks.

Ordinary technical evidence is preserved: status codes, counts,
``request_id=req_123`` style correlation strings, and error names never
match the patterns and are kept as-is. When in doubt about a whole
field, omit it rather than broadening redaction.
"""

from __future__ import annotations

import re
from typing import Any

REDACTED = "[redacted]"

_SENSITIVE_KEY = re.compile(
    r"password|passwd|secret|token|api[_-]?key|access[_-]?key|"
    r"authorization|cookie|session[_-]?(token|cookie|secret|key)|"
    r"private[_-]?key|client[_-]?secret|"
    r"credentials|^auth$|set-cookie",
    re.IGNORECASE,
)

# Credential-shaped values hiding under innocent keys.
_VALUE_PATTERNS = (
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/=]+"),
    re.compile(r"Basic\s+[A-Za-z0-9+/=]+"),
    re.compile(r"sk-(live|test)-[A-Za-z0-9]+"),
    re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        re.DOTALL,
    ),
)


def is_sensitive_key(key: str) -> bool:
    return bool(_SENSITIVE_KEY.search(key))


def scrub_value_string(value: str) -> str:
    """Redact credential-shaped substrings, keep everything else intact."""
    redacted = value
    for pattern in _VALUE_PATTERNS:
        redacted = pattern.sub(REDACTED, redacted)
    return redacted


def scrub(value: Any) -> Any:
    """Return a copy of ``value`` with sensitive entries redacted."""
    if isinstance(value, dict):
        return {
            k: REDACTED if is_sensitive_key(str(k)) else scrub(v)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [scrub(v) for v in value]
    if isinstance(value, str):
        return scrub_value_string(value)
    return value
