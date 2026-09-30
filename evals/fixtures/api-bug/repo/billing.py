"""Invoice rendering behind GET /api/v1/invoices/{id}."""

from __future__ import annotations

import json

INVOICES = {
    "inv_1": {"id": "inv_1", "total_cents": 4200, "due_date": "2026-04-01"},
    "inv_2": {"id": "inv_2", "total_cents": 900},
}


def render_invoice(invoice_id: str) -> tuple[int, str]:
    """Return (status, body) for the invoice detail endpoint."""
    invoice = INVOICES.get(invoice_id)
    if invoice is None:
        return 404, json.dumps({"error": "not_found"})
    try:
        body = {
            "id": invoice["id"],
            "total_cents": invoice["total_cents"],
            # due_date is optional in the data model, but the renderer
            # assumes it is always present.
            "due_label": f"due {invoice['due_date']}",
        }
    except KeyError:
        return 500, json.dumps({"error": "internal_error"})
    return 200, json.dumps(body)
