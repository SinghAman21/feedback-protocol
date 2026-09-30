"""Pydantic models for the Feedback Protocol v0.1.

These models mirror ``schema/feedback.schema.json`` exactly. Only ``type``
and ``summary`` are required; every other field is optional so agents are
never forced to speculate about internals they cannot know.

Unknown fields are accepted (``extra="allow"``) and preserved, per the
spec's extensibility rule: implementations MUST ignore what they do not
understand instead of rejecting it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

FeedbackType = Literal[
    "bug", "missing_feature", "unexpected_behavior", "documentation", "performance"
]

#: Protocol version advertised by the discovery endpoint (SPEC v0.1).
PROTOCOL_VERSION = "0.1"

#: Default submission path advertised by discovery.
DEFAULT_FEEDBACK_PATH = "/feedback"


class AgentInfo(BaseModel):
    """Identity of the reporting agent (`agent` field).

    Kept separate from the affected service (`service` field): the agent
    reports the problem, the service is where it was observed.
    """

    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1, description="Agent name, e.g. 'example-agent'.")
    version: str | None = Field(
        default=None, min_length=1, description="Agent version, e.g. '1.0.0'."
    )


class ServiceInfo(BaseModel):
    """The affected service (`service` field), when the reporter knows it.

    All sub-fields are optional: reporters send what they know, and
    servers normalize what is missing. Never mandatory.
    """

    model_config = ConfigDict(extra="allow")

    name: str | None = Field(default=None, min_length=1)
    version: str | None = Field(
        default=None, min_length=1, description="Service version, e.g. '4.2.1'."
    )
    environment: str | None = Field(
        default=None, min_length=1, description="E.g. 'production'."
    )


class AttemptInfo(BaseModel):
    """The API operation that surfaced the problem (`attempt` field)."""

    model_config = ConfigDict(extra="allow")

    method: str | None = Field(default=None, min_length=1, description="HTTP method used.")
    path: str | None = Field(default=None, min_length=1, description="Request path attempted.")


class ObservedInfo(BaseModel):
    """What the agent actually observed (`observed` field). Facts, not diagnosis."""

    model_config = ConfigDict(extra="allow")

    status: int | None = Field(
        default=None, ge=100, le=599, description="HTTP status code observed, if applicable."
    )


class Feedback(BaseModel):
    """A feedback submission body. Mirrors the v0.1 JSON schema 1:1."""

    model_config = ConfigDict(extra="allow")

    type: FeedbackType = Field(description="Category of feedback.")
    summary: str = Field(min_length=1, max_length=280, description="Short summary.")
    description: str | None = Field(default=None, min_length=1)
    goal: str | None = Field(default=None, min_length=1)
    attempt: AttemptInfo | None = None
    observed: ObservedInfo | None = None
    expected: str | dict[str, Any] | None = Field(
        default=None,
        description="What was reasonably expected: a statement or structured "
        "expectations (e.g. {'capability': 'pagination'}). Never a root cause.",
    )
    missing_capability: str | None = Field(default=None, min_length=1)
    suggestion: str | None = Field(default=None, min_length=1)
    agent: AgentInfo | None = None
    service: str | ServiceInfo | None = Field(
        default=None,
        description="The affected service: a plain name or an object with "
        "name/version/environment.",
    )
    request_id: str | None = Field(default=None, min_length=1)
    session_id: str | None = Field(
        default=None,
        min_length=1,
        description="Broader agent interaction this report belongs to, when available.",
    )
    trace_id: str | None = Field(
        default=None, min_length=1, description="Distributed trace ID, when available."
    )
    timestamp: datetime | None = Field(
        default=None,
        description="When the problem was observed (RFC 3339 date-time, UTC preferred).",
    )
    metadata: dict[str, Any] | None = Field(default=None)

    @field_validator("expected")
    @classmethod
    def _non_empty_expected_string(cls, v: str | dict[str, Any] | None) -> Any:
        if isinstance(v, str) and not v:
            raise ValueError("expected must be a non-empty string or an object")
        return v

    @field_validator("service")
    @classmethod
    def _non_empty_service_string(cls, v: str | ServiceInfo | None) -> Any:
        if isinstance(v, str) and not v:
            raise ValueError("service must be a non-empty name or an object")
        return v


class DiscoveryResponse(BaseModel):
    """Body of ``GET /.well-known/feedback-protocol``."""

    model_config = ConfigDict(extra="allow")

    version: str = Field(default=PROTOCOL_VERSION, description="Protocol version, e.g. '0.1'.")
    feedback_endpoint: str = Field(
        default=DEFAULT_FEEDBACK_PATH, description="Path where feedback is accepted."
    )
    methods: list[str] = Field(default_factory=lambda: ["POST"])


class FeedbackReceipt(BaseModel):
    """Minimal successful response to ``POST /feedback`` (SPEC 3.4)."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(description="Opaque server-assigned feedback identifier.")
    status: Literal["received"] = Field(default="received")


class StoredFeedback(BaseModel):
    """A feedback report as persisted by a :class:`FeedbackStore`.

    This is a server-side record, NOT part of the wire schema: it wraps the
    client-supplied :class:`Feedback` with the generated ``id`` and the
    server-side ``received_at`` timestamp. The nested ``feedback`` payload
    keeps the exact v0.1 shape so future stores (PostgreSQL, Redis, external
    services) can persist it without changing the HTTP protocol.
    """

    model_config = ConfigDict(extra="allow")

    id: str
    received_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Server-side receipt time (UTC).",
    )
    feedback: Feedback


class FeedbackTypeEnum(str, Enum):
    """Convenience enum for the five supported feedback types."""

    bug = "bug"
    missing_feature = "missing_feature"
    unexpected_behavior = "unexpected_behavior"
    documentation = "documentation"
    performance = "performance"


SUPPORTED_FEEDBACK_TYPES: tuple[str, ...] = (
    "bug",
    "missing_feature",
    "unexpected_behavior",
    "documentation",
    "performance",
)
