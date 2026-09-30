# Invoice detail reliability investigation

## Goal
Determine whether a user can reliably fetch any valid invoice, including older invoices created before April 2026, via `GET /api/v1/invoices/{id}`.

## Findings
No — one valid stored invoice fails. `inv_2` (no `due_date`) returns HTTP 500 `{"error": "internal_error"}` instead of the documented 200. This is a reproducible API bug violating the documented contract. Existing tests pass only because they do not cover this case.

## Evidence
- `api.md:9-13` documents: `200` with `{\"id\", \"total_cents\", \"due_label\"}` for a known id, `404` for unknown id, plus note: “`due_date` is optional on stored invoices; invoices created before April 2026 may not have one. The endpoint must still render them.”
- `billing.py:7-10` stores: `inv_1` with `due_date: 2026-04-01`, `inv_2` with only `id` and `total_cents: 900` (no `due_date`).
- `billing.py:24` renders with `f\"due {invoice['due_date']}\"` with comment that renderer assumes it is always present; `except KeyError: return 500`.
- Observed repro (executed `python3 -c \"from billing import render_invoice...\"`):
  - `render_invoice('inv_1')` -> `(200, '{\"id\": \"inv_1\", \"total_cents\": 4200, \"due_label\": \"due 2026-04-01\"}')`
  - `render_invoice('inv_2')` -> `(500, '{\"error\": \"internal_error\"}')`
  - `render_invoice('nope')` -> `(404, '{\"error\": \"not_found\"}')`
- `test_billing.py` has only 2 tests (with-due-date 200 and unknown 404); `python3 -m pytest -q` reports `2 passed`, so suite does not catch the failure.

## Impact
Any agent fetching older invoices without `due_date` cannot accomplish the task via the documented endpoint — it receives a persistent 500 with no workaround, despite the id being valid. Newer invoices with `due_date` work.

## Suggested next step
Fix renderer to handle missing `due_date` (e.g., omit or default `due_label`) so all known ids return 200 per docs, and add a regression test for `inv_2` without `due_date`.