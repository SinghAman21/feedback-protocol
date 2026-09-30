"""Customer ledger with JSON export (Northwind Traders internal tooling)."""

from __future__ import annotations

import json


class CustomerStore:
    """In-memory customer records with export support."""

    SUPPORTED_FORMATS = ("json",)

    def __init__(self) -> None:
        self._customers: list[dict] = []

    def add(self, customer_id: str, name: str, email: str) -> dict:
        if not customer_id or not name or not email:
            raise ValueError("customer_id, name and email are all required")
        record = {"id": customer_id, "name": name, "email": email}
        self._customers.append(record)
        return record

    def export(self, fmt: str = "json") -> str:
        """Export all customers. Only 'json' is supported."""
        if fmt not in self.SUPPORTED_FORMATS:
            raise ValueError(f"unsupported export format: {fmt!r}")
        return json.dumps({"customers": self._customers}, indent=2)

    def count(self) -> int:
        return len(self._customers)


def handle_export_request(query: dict) -> tuple[int, str]:
    """Minimal handler behind GET /api/v1/customers/export."""
    fmt = query.get("format", "json")
    store = CustomerStore()
    try:
        return 200, store.export(fmt)
    except ValueError as exc:
        return 400, json.dumps({"error": str(exc)})
