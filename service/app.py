"""Centralized feedback service: HTTP layer.

Endpoints (all require Bearer API-key auth except ``/health`` and
discovery, which stay public per the protocol):

- ``POST /feedback`` — ingest a protocol-compliant report (+ optional
  ``service`` identity). Returns ``201 {"id", "status": "received"}``.
- ``GET /feedback/{id}`` — retrieve one stored report with triage status.
- ``GET /feedback`` — list with ``service`` / ``type`` / ``status``
  filters plus ``limit`` / ``offset``.
- ``GET /services/{service}/feedback`` — list reports for one service.
- ``GET /clusters`` — deterministic groups (``service`` / ``type`` filters).
- ``GET /clusters/{cluster_id}`` — one group with members + breakdown.
- ``PATCH /feedback/{id}`` — set triage status (``{"status": ...}``).
- ``PATCH /clusters/{cluster_id}`` — set triage status for all members.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from feedback_protocol.models import (
    DEFAULT_FEEDBACK_PATH,
    PROTOCOL_VERSION,
    Feedback,
    FeedbackReceipt,
)
from service.auth import api_key_auth
from service.cluster import (
    cluster_id_for,
    cluster_status,
    group_key_for,
    normalize_summary,
)
from service.db import SqliteFeedbackStore
from service.models import (
    TRIAGE_STATUSES,
    ClusterInfo,
    FeedbackRecord,
    ServiceIdentity,
    TriageStatus,
    parse_service,
)
from service.scrub import scrub

logger = logging.getLogger("feedback-service")

DISCOVERY_PATH = "/.well-known/feedback-protocol"
DEFAULT_API_KEY = "dev-key-change-me"

_FEEDBACK_TYPES = frozenset(
    {"bug", "missing_feature", "unexpected_behavior", "documentation", "performance"}
)


def row_to_record(row: dict[str, Any]) -> FeedbackRecord:
    body = json.loads(row["body_json"])
    return FeedbackRecord(
        id=row["id"],
        service=ServiceIdentity(
            name=row["service_name"],
            version=row.get("service_version"),
            environment=row["service_env"],
        ),
        status=TriageStatus(row["status"]),
        received_at=datetime.fromisoformat(row["received_at"]),
        feedback=Feedback.model_validate(body),
        cluster_id=cluster_id_for(group_key_for(row)),
    )


def build_clusters(rows: list[dict[str, Any]]) -> list[ClusterInfo]:
    groups: dict[tuple, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(group_key_for(row), []).append(row)
    clusters = []
    for key, members in groups.items():
        service_name, ftype, method, path, capability = key
        breakdown: dict[str, int] = {}
        for m in members:
            breakdown[m["status"]] = breakdown.get(m["status"], 0) + 1
        representative = row_to_record(members[0])
        clusters.append(
            ClusterInfo(
                cluster_id=cluster_id_for(key),
                service=service_name,
                type=ftype,
                method=method or None,
                endpoint=path or None,
                missing_capability=capability or None,
                count=len(members),
                first_seen=datetime.fromisoformat(members[0]["received_at"]),
                last_seen=datetime.fromisoformat(members[-1]["received_at"]),
                status=cluster_status([m["status"] for m in members]),
                status_breakdown=breakdown,
                representative=representative,
                feedback_ids=[m["id"] for m in members],
            )
        )
    clusters.sort(key=lambda c: (-c.count, c.last_seen.isoformat()), reverse=False)
    return clusters


def create_app(
    db_path: str = "feedback-service.db", api_key: str = DEFAULT_API_KEY
) -> FastAPI:
    store = SqliteFeedbackStore(db_path)
    auth = api_key_auth(api_key)
    app = FastAPI(title="Feedback Protocol central service")
    app.state.store = store  # operator/test access; not part of the protocol

    def err(status_code: int, detail: str, **extra: Any) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": detail, **extra})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get(DISCOVERY_PATH)
    def discovery() -> dict[str, Any]:
        return {
            "version": PROTOCOL_VERSION,
            "feedback_endpoint": DEFAULT_FEEDBACK_PATH,
            "methods": ["POST"],
        }

    @app.post("/feedback", status_code=201, dependencies=[auth])
    async def ingest(request: Request) -> JSONResponse:
        try:
            raw = await request.body()
        except Exception:
            return err(400, "Unable to read request body.")
        if not raw:
            return err(400, "Request body must be a JSON object.")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return err(400, "Request body must be valid JSON.")
        if not isinstance(payload, dict):
            return err(400, "Request body must be a JSON object.")

        service = parse_service(payload.pop("service", None))
        try:
            feedback = Feedback.model_validate(payload)
        except ValidationError as exc:
            return err(
                400, "Invalid feedback payload.", errors=exc.errors(include_url=False)
            )

        if feedback.timestamp is None:
            feedback = feedback.model_copy(
                update={"timestamp": datetime.now(timezone.utc)}
            )
        scrubbed = scrub(feedback.model_dump(mode="json"))
        row = store.save(
            feedback=feedback,
            service_name=service.name,
            service_env=service.environment,
            service_version=service.version,
            session_id=feedback.session_id,
            trace_id=feedback.trace_id,
            normalized_summary=normalize_summary(feedback.summary),
            body_json=json.dumps(scrubbed),
        )
        # Privacy: log routing metadata only — never payloads or credentials.
        logger.info(
            "feedback stored id=%s type=%s service=%s",
            row["id"],
            row["type"],
            row["service_name"],
        )
        receipt = FeedbackReceipt(id=row["id"], status="received")
        return JSONResponse(status_code=201, content=receipt.model_dump())

    def record_or_404(feedback_id: str) -> Any:
        row = store.get(feedback_id)
        if row is None:
            return err(404, "Feedback not found.")
        return row_to_record(row)

    @app.get("/feedback/{feedback_id}", dependencies=[auth])
    def get_feedback(feedback_id: str) -> Any:
        result = record_or_404(feedback_id)
        if isinstance(result, JSONResponse):
            return result
        return result

    @app.get("/feedback", dependencies=[auth])
    def list_feedback(
        service: str | None = None,
        type: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Any:
        if type is not None and type not in _FEEDBACK_TYPES:
            return err(
                400, f"Invalid type filter. Must be one of: {', '.join(sorted(_FEEDBACK_TYPES))}."
            )
        if status is not None and status not in TRIAGE_STATUSES:
            return err(
                400, f"Invalid status filter. Must be one of: {', '.join(TRIAGE_STATUSES)}."
            )
        if limit < 1 or limit > 1000 or offset < 0:
            return err(400, "Invalid pagination: 1 <= limit <= 1000, offset >= 0.")
        rows, total = store.list(
            service=service, type=type, status=status, limit=limit, offset=offset
        )
        return {
            "items": [row_to_record(r).model_dump(mode="json") for r in rows],
            "total": total,
        }

    @app.get("/services/{service_name}/feedback", dependencies=[auth])
    def list_service_feedback(
        service_name: str,
        type: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Any:
        return list_feedback(
            service=service_name, type=type, status=status, limit=limit, offset=offset
        )

    def clusters_filtered(
        service: str | None, type: str | None
    ) -> Any:
        if type is not None and type not in _FEEDBACK_TYPES:
            return err(
                400, f"Invalid type filter. Must be one of: {', '.join(sorted(_FEEDBACK_TYPES))}."
            )
        rows = store.all_for_clustering(service=service, type=type)
        return build_clusters(rows)

    @app.get("/clusters", dependencies=[auth])
    def list_clusters(
        service: str | None = None, type: str | None = None
    ) -> Any:
        result = clusters_filtered(service, type)
        if isinstance(result, JSONResponse):
            return result
        return {
            "items": [c.model_dump(mode="json") for c in result],
            "total": len(result),
        }

    @app.get("/clusters/{cluster_id}", dependencies=[auth])
    def get_cluster(
        cluster_id: str, service: str | None = None, type: str | None = None
    ) -> Any:
        result = clusters_filtered(service, type)
        if isinstance(result, JSONResponse):
            return result
        for cluster in result:
            if cluster.cluster_id == cluster_id:
                return cluster
        return err(404, "Cluster not found.")

    @app.patch("/feedback/{feedback_id}", dependencies=[auth])
    async def update_status(feedback_id: str, request: Request) -> JSONResponse:
        try:
            payload = json.loads(await request.body() or b"{}")
        except json.JSONDecodeError:
            return err(400, "Request body must be valid JSON.")
        new_status = payload.get("status") if isinstance(payload, dict) else None
        if new_status not in TRIAGE_STATUSES:
            return err(
                400, f"Invalid status. Must be one of: {', '.join(TRIAGE_STATUSES)}."
            )
        row = store.set_status(feedback_id, new_status)
        if row is None:
            return err(404, "Feedback not found.")
        return JSONResponse(
            status_code=200, content=row_to_record(row).model_dump(mode="json")
        )

    @app.patch("/clusters/{cluster_id}", dependencies=[auth])
    async def update_cluster_status(cluster_id: str, request: Request) -> JSONResponse:
        try:
            payload = json.loads(await request.body() or b"{}")
        except json.JSONDecodeError:
            return err(400, "Request body must be valid JSON.")
        new_status = payload.get("status") if isinstance(payload, dict) else None
        if new_status not in TRIAGE_STATUSES:
            return err(
                400, f"Invalid status. Must be one of: {', '.join(TRIAGE_STATUSES)}."
            )
        clusters = build_clusters(store.all_for_clustering())
        target = next((c for c in clusters if c.cluster_id == cluster_id), None)
        if target is None:
            return err(404, "Cluster not found.")
        updated = store.set_status_for_ids(target.feedback_ids, new_status)
        return JSONResponse(
            status_code=200,
            content={"cluster_id": cluster_id, "status": new_status, "updated": updated},
        )

    return app


def create_default_app() -> FastAPI:
    """Build the service app from environment (used by uvicorn --factory)."""
    api_key = os.environ.get("FEEDBACK_SERVICE_API_KEY", DEFAULT_API_KEY)
    if api_key == DEFAULT_API_KEY:
        logger.warning(
            "Using default dev API key. Set FEEDBACK_SERVICE_API_KEY in production."
        )
    return create_app(
        db_path=os.environ.get("FEEDBACK_SERVICE_DB", "feedback-service.db"),
        api_key=api_key,
    )
