# Members API

## DELETE /api/v1/members/{id}

Remove exactly one member.

Bulk delete is **not supported** by design: removal requires per-member
audit approval, so deletions happen one at a time.

Rate limiting: 100 requests/minute per workspace. This limit is
intentional abuse protection, not a defect. `429` responses include
`retry_after_s`.

Responses:

- `200` with `{"removed": "<id>"}` on success.
- `404` for an unknown id.
- `429` with `{"error": "rate_limited"}` when the quota is exceeded.
