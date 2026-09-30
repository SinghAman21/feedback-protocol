# Invoices API

## GET /api/v1/invoices/{id}

Return one invoice.

Responses:

- `200` with `{"id", "total_cents", "due_label"}` for a known id.
- `404` with `{"error": "not_found"}` for an unknown id.

Note: `due_date` is optional on stored invoices; invoices created
before April 2026 may not have one. The endpoint must still render them.
