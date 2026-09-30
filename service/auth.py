"""Basic authentication for the centralized service.

All management endpoints require ``Authorization: Bearer <api-key>``.
Only ``GET /health`` and ``GET /.well-known/feedback-protocol``
(discovery, which must stay public per the protocol) are open.

This is intentionally minimal: a single shared key from the
``FEEDBACK_SERVICE_API_KEY`` environment variable. It keeps feedback
from being publicly exposed without pretending to be a full identity
system. Production deployments handling sensitive data should put this
service behind their own SSO / gateway auth and short-lived credentials.
"""

from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException, Request, status


def api_key_auth(api_key: str) -> Depends:
    """Build a FastAPI dependency enforcing the shared API key."""

    async def require_key(request: Request) -> None:
        auth = request.headers.get("authorization", "")
        scheme, _, token = auth.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or malformed Authorization header.",
            )
        if not secrets.compare_digest(token, api_key):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key.",
            )

    return Depends(require_key)
