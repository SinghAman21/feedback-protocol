"""Service-side models for the centralized feedback service.

The wire format stays v0.1: ingestion accepts a protocol-compliant body
(only ``type`` + ``summary`` required) plus an optional ``service``
identifier. Everything below wraps that payload with server-side
concerns (identity, triage status, clustering) without changing the
protocol.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from feedback_protocol.models import Feedback


class TriageStatus(str, Enum):
    """Manual triage state of a stored report.

    Reports are NOT confirmed issues: ``new`` means "received, unread".
    ``accepted`` means a human confirmed a real problem worth fixing.
    Nothing here is ever set automatically.
    """

    new = "new"
    investigating = "investigating"
    accepted = "accepted"
    rejected = "rejected"
    resolved = "resolved"


TRIAGE_STATUSES: tuple[str, ...] = tuple(s.value for s in TriageStatus)


class ServiceIdentity(BaseModel):
    """Which participating service the feedback is about.

    Accepts a plain string (``"payments-api"``) or an object
    (``{"name": "payments-api", "environment": "production"}``).
    Extra keys are preserved so the model stays extensible.
    """

    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1)
    environment: str | None = Field(default=None, min_length=1)


def parse_service(value: Any) -> ServiceIdentity:
    """Normalize the ``service`` ingestion field to a ServiceIdentity.

    Missing/empty values become ``{"name": "unknown"}`` so ingestion
    never fails for lack of identity.
    """
    if value is None or value == "":
        return ServiceIdentity(name="unknown")
    if isinstance(value, str):
        return ServiceIdentity(name=value)
    if isinstance(value, dict):
        name = value.get("name")
        if not isinstance(name, str) or not name:
            return ServiceIdentity(name="unknown")
        rest = {k: v for k, v in value.items() if k != "name"}
        return ServiceIdentity(name=name, **rest)
    return ServiceIdentity(name="unknown")


class FeedbackRecord(BaseModel):
    """A stored report as returned by the service API."""

    model_config = ConfigDict(extra="allow")

    id: str
    service: ServiceIdentity
    status: TriageStatus = TriageStatus.new
    received_at: datetime
    feedback: Feedback


class ClusterInfo(BaseModel):
    """A deterministic group of reports about the same underlying problem."""

    model_config = ConfigDict(extra="allow")

    cluster_id: str
    service: str
    type: str
    method: str | None = None
    endpoint: str | None = None
    missing_capability: str | None = None
    count: int
    first_seen: datetime
    last_seen: datetime
    status_breakdown: dict[str, int] = Field(default_factory=dict)
    representative: FeedbackRecord
    feedback_ids: list[str] = Field(default_factory=list)
