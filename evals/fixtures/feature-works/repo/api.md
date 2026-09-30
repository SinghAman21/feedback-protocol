# Customers API

## GET /api/v1/customers/export

Export all customers as JSON.

Query parameters:

- `format` (optional, default `"json"`): only `"json"` is supported.
  Any other value returns `400 Bad Request` with an error body.

Responses:

- `200` with `{"customers": [...]}` on success.
- `400` with `{"error": "..."}` for unsupported formats.

Example:

```text
GET /api/v1/customers/export?format=json
```
