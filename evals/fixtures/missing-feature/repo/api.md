# Subscribers API

## GET /api/v1/subscribers/export

Export the subscriber list as JSON.

Query parameters:

- `format` (optional, default `"json"`): only `"json"` is supported.

Responses:

- `200` with `{"subscribers": [...]}` on success.
- `400` with `{"error": "unsupported export format: ..."}` otherwise.

The marketing team currently copies JSON into a spreadsheet by hand.
