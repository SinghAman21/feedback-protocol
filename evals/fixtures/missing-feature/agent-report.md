# Subscriber CSV Export Investigation

## Goal
Determine whether a user can reliably export subscriber data as CSV for the marketing team via `GET /api/v1/subscribers/export`.

## Findings
No reliable CSV export exists. The implementation supports only JSON. Requesting CSV is rejected with `400 unsupported export format`. This is a missing capability, not a transient or user error — the API works as documented but cannot satisfy the legitimate marketing goal.

## Evidence
- `api.md:9`: `format (optional, default \"json\"): only \"json\" is supported.`
- `api.md:14`: `400 with {\"error\": \"unsupported export format: ...\"} otherwise.`
- `api.md:16`: `The marketing team currently copies JSON into a spreadsheet by hand.`
- `subscribers.py:11`: `SUPPORTED_FORMATS = (\"json\",)`
- `subscribers.py:23-26`: `def export(self, fmt: str = \"json\")` raises `ValueError(f\"unsupported export format: {fmt!r}\")` for non-json.
- `test_subscribers.py:18-30`: `test_export_rejects_csv` and `test_handler_returns_400_for_csv` assert CSV is rejected.
- Live repro: `handle_export_request({\"format\": \"csv\"})` returned `(400, '{\"error\": \"unsupported export format: \\'csv\\'\"}')`.
- Tests: `python -m pytest -v` → `4 passed`.

## Impact
An agent cannot accomplish CSV export for the marketing team. Manual JSON-to-spreadsheet copying remains required, which is error-prone and unscalable for bulk lists.

## Suggested next step
Add `csv` to supported export formats for `GET /api/v1/subscribers/export?format=csv`, returning RFC4180 CSV with header and email,name rows, and update docs and tests accordingly. Filed as missing_feature; not fixed yet.