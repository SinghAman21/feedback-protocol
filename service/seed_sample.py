#!/usr/bin/env python3
"""Seed the central service with the v0.5 sample data (stdlib only).

Three reports about the same underlying problem — the users endpoint
has no pagination — from three different reporters:

- Reporter A: "GET /users is too large"          (missing_feature)
- Reporter B: "GET /users needs pagination"      (missing_feature)
- Reporter C: "GET /users returned 100k records" (missing_feature)

All three share service + type + method + endpoint + missing
capability, so deterministic grouping puts them in ONE cluster.

Usage:
    python service/seed_sample.py [base_url] [api_key]
    python service/seed_sample.py http://localhost:8001 dev-key-change-me
"""

from __future__ import annotations

import json
import sys
import urllib.request

REPORTS = [
    {
        "service": {"name": "users-api", "environment": "production"},
        "type": "missing_feature",
        "summary": "GET /users is too large",
        "goal": "Export the user list for billing",
        "attempt": {"method": "GET", "path": "/api/v1/users"},
        "observed": {"status": 200, "item_count": 100000},
        "missing_capability": "pagination",
        "suggestion": "Support cursor-based pagination",
        "agent": {"name": "reporter-a", "version": "1.0.0"},
    },
    {
        "service": "users-api",
        "type": "missing_feature",
        "summary": "GET /users needs pagination",
        "goal": "Page through users in the admin UI",
        "attempt": {"method": "GET", "path": "/api/v1/users"},
        "observed": {"status": 200, "item_count": 100000},
        "missing_capability": "pagination",
        "suggestion": "Support cursor-based pagination",
        "agent": {"name": "reporter-b", "version": "2.1.0"},
    },
    {
        "service": {"name": "users-api", "environment": "production"},
        "type": "missing_feature",
        "summary": "GET /users returned 100k records",
        "goal": "Sync users to the warehouse",
        "attempt": {"method": "GET", "path": "/api/v1/users"},
        "observed": {"status": 200, "item_count": 100000},
        "missing_capability": "pagination",
        "agent": {"name": "reporter-c", "version": "0.9.0"},
    },
]


def post(base: str, key: str, payload: dict) -> dict:
    req = urllib.request.Request(
        f"{base}/feedback",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def get(base: str, key: str, path: str) -> dict:
    req = urllib.request.Request(
        f"{base}{path}", headers={"Authorization": f"Bearer {key}"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def main() -> None:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8001"
    key = sys.argv[2] if len(sys.argv) > 2 else "dev-key-change-me"
    ids = [post(base, key, r)["id"] for r in REPORTS]
    print(f"stored {len(ids)} reports: {', '.join(ids)}")
    clusters = get(base, key, "/clusters")
    for c in clusters["items"]:
        print(
            f'{c["cluster_id"]}: service={c["service"]} type={c["type"]} '
            f'endpoint={c["endpoint"]} count={c["count"]}'
        )


if __name__ == "__main__":
    main()
