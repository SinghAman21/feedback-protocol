"""Account creation behind POST /api/v1/accounts."""

from __future__ import annotations

import json

_ACCOUNTS: dict[str, dict] = {}


def create_account(payload: dict) -> tuple[int, str]:
    """Create one account. Requires exactly the documented fields."""
    email = payload.get("email")
    name = payload.get("name", "")
    if not isinstance(email, str) or "@" not in email:
        return 400, json.dumps({"error": "email must be a valid email address"})
    account_id = f"acct_{len(_ACCOUNTS) + 1}"
    _ACCOUNTS[account_id] = {"id": account_id, "email": email, "name": name}
    return 201, json.dumps(_ACCOUNTS[account_id])
