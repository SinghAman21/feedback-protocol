"""Minimal runnable FastAPI service exposing the Feedback Protocol.

Run with::

    pip install feedback-protocol uvicorn
    uvicorn app:app --reload --port 8000

Then::

    curl http://localhost:8000/.well-known/feedback-protocol
    curl -X POST http://localhost:8000/feedback \\
      -H 'Content-Type: application/json' \\
      -d '{"type":"missing_feature","summary":"Users endpoint does not support pagination"}'
"""

from fastapi import Depends, FastAPI

from feedback_protocol.fastapi import create_feedback_router
from feedback_protocol.store import InMemoryFeedbackStore

store = InMemoryFeedbackStore()

# --- Optional authentication extension point --------------------------------
# The protocol does not mandate an auth mechanism. Uncomment and adapt for
# production, e.g. API-key or OAuth2 verification:
#
#   from fastapi import Header, HTTPException
#
#   async def verify_api_key(x_api_key: str = Header(default="")) -> None:
#       if x_api_key != "secret":
#           raise HTTPException(status_code=401, detail="Invalid API key.")
#
#   feedback_router = create_feedback_router(
#       store=store, dependencies=[Depends(verify_api_key)]
#   )
feedback_router = create_feedback_router(store=store)

app = FastAPI(title="Feedback Protocol example")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(feedback_router)


# Operator-only debug endpoint (NOT part of the protocol): lets you confirm
# what was stored while developing locally. Remove or protect in production.
@app.get("/debug/feedback-count")
async def feedback_count() -> dict[str, int]:
    return {"count": await store.count()}


def _auth_example() -> Depends:  # pragma: no cover - documentation helper
    """Example of how to protect the router (not wired in by default)."""

    async def verify() -> None:
        return None

    return Depends(verify)
