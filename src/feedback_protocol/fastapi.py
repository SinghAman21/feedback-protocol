"""FastAPI integration for the Feedback Protocol.

Minimal usage::

    from fastapi import FastAPI
    from feedback_protocol.fastapi import feedback_router

    app = FastAPI()
    app.include_router(feedback_router)

This exposes::

    GET  /.well-known/feedback-protocol   (canonical, SPEC v0.1)
    POST /feedback                        (201 + {"id": ..., "status": "received"})

Authentication:
    This package deliberately provides NO authentication mechanism.
    Protect the router with standard FastAPI dependencies::

        from fastapi import Depends
        from feedback_protocol.fastapi import create_feedback_router

        async def verify_api_key(...): ...

        router = create_feedback_router(dependencies=[Depends(verify_api_key)])
        app.include_router(router)

Privacy:
    Received payloads are never logged in full — only the generated ID and
    the feedback ``type`` are logged. See README "Production considerations".
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from feedback_protocol.models import (
    DEFAULT_FEEDBACK_PATH,
    PROTOCOL_VERSION,
    DiscoveryResponse,
    Feedback,
    FeedbackReceipt,
)
from feedback_protocol.store import FeedbackStore, InMemoryFeedbackStore

logger = logging.getLogger(__name__)

#: Canonical discovery path (normative, SPEC v0.1 section 2).
DISCOVERY_PATH = "/.well-known/feedback-protocol"


def _discovery_payload(feedback_path: str, protocol_version: str) -> dict[str, Any]:
    return DiscoveryResponse(
        version=protocol_version,
        feedback_endpoint=feedback_path,
        methods=["POST"],
    ).model_dump()


def create_feedback_router(
    store: FeedbackStore | None = None,
    *,
    feedback_path: str = DEFAULT_FEEDBACK_PATH,
    protocol_version: str = PROTOCOL_VERSION,
    dependencies: list[Depends] | None = None,
) -> APIRouter:
    """Create a FastAPI router exposing the Feedback Protocol endpoints.

    Args:
        store: Persistence backend. Defaults to a new
            :class:`InMemoryFeedbackStore`. Pass a custom
            :class:`FeedbackStore` (PostgreSQL, Redis, external service)
            without changing the HTTP protocol.
        feedback_path: Path for submissions (default ``/feedback``). The
            discovery document advertises whatever value is given here.
        protocol_version: Protocol version string for discovery
            (default ``"0.1"`` — the spec version, not the package version).
        dependencies: Optional FastAPI dependencies applied to both
            endpoints (e.g. authentication). See module docstring.

    Returns:
        A configured :class:`fastapi.APIRouter` ready for
        ``app.include_router(...)``.
    """
    active_store = store if store is not None else InMemoryFeedbackStore()
    deps = dependencies or []
    router = APIRouter()

    async def _discovery() -> dict[str, Any]:
        return _discovery_payload(feedback_path, protocol_version)

    router.add_api_route(
        DISCOVERY_PATH,
        _discovery,
        methods=["GET"],
        response_model=DiscoveryResponse,
        summary="Discover Feedback Protocol support",
        dependencies=deps,
    )

    async def _submit(request: Request) -> Response:
        # Read the raw body so malformed JSON maps to 400 (SPEC 3.5),
        # not FastAPI's default 422.
        try:
            raw = await request.body()
        except Exception:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "Unable to read request body."},
            )
        if not raw:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "Request body must be a JSON object."},
            )
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "Request body must be valid JSON."},
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "Request body must be a JSON object."},
            )
        try:
            feedback = Feedback.model_validate(payload)
        except ValidationError as exc:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "detail": "Invalid feedback payload.",
                    "errors": exc.errors(include_url=False),
                },
            )

        record = await active_store.save(feedback)
        # Privacy: log routing metadata only — never the payload, headers,
        # cookies, tokens, or any credential material.
        logger.info("feedback received id=%s type=%s", record.id, record.feedback.type)
        receipt = FeedbackReceipt(id=record.id, status="received")
        return JSONResponse(status_code=status.HTTP_201_CREATED, content=receipt.model_dump())

    router.add_api_route(
        feedback_path,
        _submit,
        methods=["POST"],
        status_code=status.HTTP_201_CREATED,
        summary="Submit feedback",
        dependencies=deps,
        responses={
            400: {"description": "Invalid feedback payload."},
            201: {"description": "Feedback received."},
        },
    )

    # Attach the store for tests/operators (not part of the wire protocol).
    router.state_store = active_store  # type: ignore[attr-defined]
    return router


#: Default in-memory store backing the prebuilt ``feedback_router``.
default_store: InMemoryFeedbackStore = InMemoryFeedbackStore()

#: Prebuilt router for the minimal ``app.include_router(feedback_router)``
#: developer experience. For custom stores/auth, use
#: :func:`create_feedback_router` instead.
feedback_router: APIRouter = create_feedback_router(store=default_store)
