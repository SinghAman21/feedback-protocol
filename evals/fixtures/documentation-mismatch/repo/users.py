"""User management routes (directory service)."""

from __future__ import annotations

import json

ROUTES = {
    ("GET", "/api/v1/users"): "list_users",
    ("GET", "/api/v1/users/{id}"): "get_user",
    ("POST", "/api/v1/users"): "create_user",
    ("POST", "/api/v1/users/{id}/delete"): "delete_user",
}

_USERS = {"u1": {"id": "u1", "name": "Ann"}}


def dispatch(method: str, path: str, body: dict | None = None) -> tuple[int, str]:
    """Tiny router used by the directory service."""
    for (route_method, route_path), handler in ROUTES.items():
        pattern = route_path.replace("{id}", "[^/]+")
        import re

        if method == route_method and re.fullmatch(pattern, path):
            if handler == "delete_user":
                user_id = path.rstrip("/").split("/")[-2]
                if user_id in _USERS:
                    del _USERS[user_id]
                    return 200, json.dumps({"deleted": user_id})
                return 404, json.dumps({"error": "not_found"})
            if handler == "get_user":
                user_id = path.rstrip("/").split("/")[-1]
                if user_id in _USERS:
                    return 200, json.dumps(_USERS[user_id])
                return 404, json.dumps({"error": "not_found"})
            return 200, json.dumps({"ok": True})
    return 404, json.dumps({"error": "unknown_route"})
