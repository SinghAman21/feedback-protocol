"""feedback_protocol — Python implementation of the Feedback Protocol (v0.1 spec)."""

from feedback_protocol.models import (
    DEFAULT_FEEDBACK_PATH,
    PROTOCOL_VERSION,
    SUPPORTED_FEEDBACK_TYPES,
    AgentInfo,
    AttemptInfo,
    DiscoveryResponse,
    Feedback,
    FeedbackReceipt,
    FeedbackTypeEnum,
    ObservedInfo,
    ServiceInfo,
    StoredFeedback,
)
from feedback_protocol.ids import generate_feedback_id, is_feedback_id
from feedback_protocol.store import FeedbackStore, InMemoryFeedbackStore

__version__ = "0.2.0"

__all__ = [
    "__version__",
    "PROTOCOL_VERSION",
    "DEFAULT_FEEDBACK_PATH",
    "SUPPORTED_FEEDBACK_TYPES",
    "AgentInfo",
    "AttemptInfo",
    "DiscoveryResponse",
    "Feedback",
    "FeedbackReceipt",
    "FeedbackTypeEnum",
    "FeedbackStore",
    "InMemoryFeedbackStore",
    "ObservedInfo",
    "ServiceInfo",
    "StoredFeedback",
    "generate_feedback_id",
    "is_feedback_id",
]
