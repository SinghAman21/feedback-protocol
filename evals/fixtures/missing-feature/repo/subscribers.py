"""Subscriber list with JSON export (newsletter tooling)."""

from __future__ import annotations

import json


class SubscriberList:
    """Holds newsletter subscribers and exports them as JSON."""

    SUPPORTED_FORMATS = ("json",)

    def __init__(self) -> None:
        self._subscribers: list[dict] = []

    def subscribe(self, email: str, name: str = "") -> dict:
        if "@" not in email:
            raise ValueError("a valid email address is required")
        record = {"email": email, "name": name}
        self._subscribers.append(record)
        return record

    def export(self, fmt: str = "json") -> str:
        """Export all subscribers. Only 'json' is implemented."""
        if fmt not in self.SUPPORTED_FORMATS:
            raise ValueError(f"unsupported export format: {fmt!r}")
        return json.dumps({"subscribers": self._subscribers}, indent=2)


def handle_export_request(query: dict) -> tuple[int, str]:
    """Minimal handler behind GET /api/v1/subscribers/export."""
    try:
        return 200, SubscriberList().export(query.get("format", "json"))
    except ValueError as exc:
        return 400, json.dumps({"error": str(exc)})
