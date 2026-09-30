# Accounts API

## POST /api/v1/accounts

Create one account.

Request body (JSON):

- `email` (required): a valid email address.
- `name` (optional): display name.

Responses:

- `201` with the created account.
- `400` with `{"error": "email must be a valid email address"}` when
  `email` is missing or malformed. Field names are exact: `e-mail`,
  `Email`, and `mail` are not accepted.
