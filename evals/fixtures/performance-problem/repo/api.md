# Events API

## GET /api/v1/events

Return a page of audit events.

Query parameters:

- `limit` (optional, default `50`, max `100`)
- `page` (optional, default `1`)

Responses:

- `200` with `{"events": [...], "page": 1, "limit": 50}` on success.

**Performance budget:** p99 under 500ms for event listing.
