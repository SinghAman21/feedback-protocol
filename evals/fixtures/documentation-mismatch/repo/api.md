# Users API

## DELETE /api/v1/users/{id}

Delete a user.

Responses:

- `200` with `{"deleted": "<id>"}` on success.
- `404` with `{"error": "not_found"}` for an unknown id.

Example:

```text
DELETE /api/v1/users/u1
```
