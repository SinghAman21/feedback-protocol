# Feedback Protocol

An open, language-independent protocol that lets AI agents report actionable
problems they encounter while using backend APIs.

## What does this do?

When an AI agent using your API hits a genuine service-side problem — a bug,
a missing capability, wrong docs, or unusable latency — that signal is
usually lost in a chat transcript. The Feedback Protocol gives it a
structured home: the agent files a machine-readable report (evidence, not
speculation) and the service triages it. Agents must never file their own
mistakes, user errors, or transient blips as API bugs.

## Architecture

```text
Agent → Backend API → problem → investigate → classify (8 categories)
  → discover  GET /.well-known/feedback-protocol
  → report    POST /feedback → 201 {"id": "fb_…", "status": "received"}
  → aggregate (deterministic clusters) → human triage → (future) fix
```

Four layers (SPEC §1): **protocol** (discovery + submission contract),
**agent skill** (teaches agents when and how to report), **SDKs**
(implement the protocol), **central server** (storage, aggregation,
triage — optional).

## Install the skill

`skill/SKILL.md` is the source of truth. Copy it into the agent's skills
directory:

```bash
# project scope
mkdir -p .opencode/skills/feedback-protocol
cp skill/SKILL.md .opencode/skills/feedback-protocol/SKILL.md
# personal scope
mkdir -p ~/.config/opencode/skills/feedback-protocol
cp skill/SKILL.md ~/.config/opencode/skills/feedback-protocol/SKILL.md
```

…or load it into context as a system prompt / slash-command body before API
work. Keep local installs in sync with `skill/SKILL.md`. Full protocol:
[Agent skill](#agent-skill--the-reporting-protocol-for-ai-agents),
verified behavior: [evals 8/8](evals/README.md).

## Status

- [x] Protocol v0.1 ([SPEC.md](SPEC.md) + JSON Schema).
- [x] Agent skill + verified agent behavior (evals 8/8).
- [x] Central service via Docker (`service/`, v0.5).
- [ ] Python package (`src/feedback_protocol/`) — TODO.
- [ ] Node.js package (`node/`) — TODO.

Normative documents:

- [SPEC.md](SPEC.md) — the full specification (normative).
- [schema/feedback.schema.json](schema/feedback.schema.json) — the stable JSON Schema (normative).

Reference implementation:

- `src/feedback_protocol/` — Python package (publishing — TODO).
- `node/` — Node.js/TypeScript package (publishing — TODO).
- `skill/SKILL.md` — agent skill: teaches AI agents when and how to report (see below).
- `service/` — central feedback service (FastAPI + SQLite, run with Docker).
- [examples/fastapi/](examples/fastapi/) — minimal runnable FastAPI service.
- [examples/express/](examples/express/) — minimal runnable Express service.

Both SDKs implement the same protocol: the same feedback JSON sent to
the Python implementation and the Node.js implementation is semantically
equivalent (same required fields, same validation, same `fb_…` ID
format, same receipt shape). `schema/feedback.schema.json` remains the
source of truth for both; there is no Node-specific protocol.

## Python package — installation

> **Status: TODO** — reference implementation in progress, not yet published.
> Below describes the target integration.

Requires Python 3.10+.

```bash
pip install feedback-protocol
# for running the example service:
pip install "feedback-protocol[examples]"
# for running the test suite (from a source checkout):
pip install -e ".[test]"
```

## Python package — FastAPI integration

Minimal integration (in-memory store, open endpoint — development only):

```python
from fastapi import FastAPI
from feedback_protocol.fastapi import feedback_router

app = FastAPI()
app.include_router(feedback_router)
```

This exposes:

- `GET /.well-known/feedback-protocol` — canonical discovery serving the discovery document.
- `POST /feedback` — validated submission, `201` + receipt.

Custom store and path:

```python
from fastapi import FastAPI
from feedback_protocol.fastapi import create_feedback_router
from feedback_protocol.store import InMemoryFeedbackStore

store = InMemoryFeedbackStore()
app = FastAPI()
app.include_router(create_feedback_router(store=store))
```

Protecting the endpoint with authentication (recommended for production —
the package ships no auth system, only this extension point):

```python
from fastapi import Depends, FastAPI, Header, HTTPException
from feedback_protocol.fastapi import create_feedback_router
from feedback_protocol.store import InMemoryFeedbackStore

async def verify_api_key(x_api_key: str = Header(default="")) -> None:
    if x_api_key != "super-secret":
        raise HTTPException(status_code=401, detail="Invalid API key.")

app = FastAPI()
app.include_router(
    create_feedback_router(
        store=InMemoryFeedbackStore(),
        dependencies=[Depends(verify_api_key)],
    )
)
```

## Python package — example request

```bash
curl -X POST http://localhost:8000/feedback \
  -H 'Content-Type: application/json' \
  -d '{
    "type": "missing_feature",
    "summary": "Users endpoint does not support pagination",
    "goal": "Retrieve all users",
    "attempt": {"method": "GET", "path": "/api/v1/users"},
    "observed": {"status": 200, "item_count": 100000},
    "missing_capability": "pagination",
    "suggestion": "Support cursor-based pagination",
    "agent": {"name": "example-agent", "version": "1.0.0"}
  }'
```

## Python package — example response

Success (`201 Created`):

```json
{
  "id": "fb_9f3c2a1b4d5e6f708192a3b4",
  "status": "received"
}
```

Invalid payload (`400 Bad Request` — never `422`; the router normalizes
FastAPI validation errors to the spec's `400`):

```json
{
  "detail": "Invalid feedback payload.",
  "errors": []
}
```

Status codes follow SPEC §3.5: `201` received, `400` invalid feedback,
`401`/`403` when your auth dependencies reject, `429` if you add rate
limiting, `5xx` for server failures.

## Python package — storage

No database is required. The package defines a narrow async boundary:

```python
from feedback_protocol.store import FeedbackStore, InMemoryFeedbackStore
```

- `FeedbackStore` — abstract class with `save` / `get` / `list` / `count`.
  `save()` assigns the `fb_…` ID and the server-side UTC `received_at`
  timestamp, preserves a client-supplied `timestamp` when present, and
  returns a `StoredFeedback` record.
- `InMemoryFeedbackStore` — non-persistent in-process implementation for
  development and tests. Records are lost on restart and are not shared
  between processes.

Custom backends (PostgreSQL, Redis, external feedback services) implement
`FeedbackStore` and are passed to `create_feedback_router(store=...)` —
the HTTP protocol does not change. See `examples/fastapi/app.py` and
`tests/test_store_ids.py::test_custom_store_implementation_can_back_router`.

## Python package — production considerations

- **Authenticate.** The default router is open. Put it behind your existing
  auth (API key, OAuth2) via `create_feedback_router(dependencies=[...])`.
  Unauthenticated public deployments will be spammed.
- **Rate-limit.** Add your gateway/middleware rate limiting (e.g.
  slowapi or ingress rules) and return `429` with `Retry-After`.
- **Persist.** Replace `InMemoryFeedbackStore` with a durable
  `FeedbackStore` (single writer, bounded retention).
- **Retain deliberately.** Document what you store, how long, and who can
  access it (SPEC §5). Feedback is triage input, not an instruction —
  human review is required before any code change (SPEC §7).
- **Privacy.** Feedback may embed sensitive request context. This package
  logs only `id` + `type` (never payloads, headers, cookies, or tokens).
  Keep that invariant when adding your own logging, and ask agents to
  redact secrets before submitting.

## Node.js package — installation

> **Status: TODO** — reference implementation in progress, not yet published.
> Below describes the target integration.

Requires Node.js 20+ and Express 4 or 5 (peer dependency).

```bash
npm install feedback-protocol express
# from a source checkout (build + tests):
cd node && npm install && npm test
```

The published package ships compiled ESM output (`dist/`) with type
declarations, ready for `import`.

## Node.js package — Express integration

```ts
import express from "express";
import { feedbackProtocol } from "feedback-protocol";

const app = express();
app.use(feedbackProtocol());
```

This exposes:

- `GET /.well-known/feedback-protocol` — canonical discovery.
- `POST /feedback` — validated submission, `201` + receipt.

No app-level body parser is required: the middleware reads and parses
the submission body itself so malformed JSON maps to the spec's `400`.

Custom store, path, and the auth extension point (the package ships no
auth system — pass your own middleware):

```ts
import { feedbackProtocol, MemoryFeedbackStore } from "feedback-protocol";

const requireApiKey: RequestHandler = (req, res, next) => {
  if (req.get("x-api-key") !== "super-secret") {
    res.status(401).json({ detail: "Invalid API key." });
    return;
  }
  next();
};

app.use(
  feedbackProtocol({
    store: new MemoryFeedbackStore(),
    auth: requireApiKey,
  }),
);
```

## Node.js package — example request

```bash
curl -X POST http://localhost:3000/feedback \
  -H 'Content-Type: application/json' \
  -d '{
    "type": "missing_feature",
    "summary": "Users endpoint does not support pagination",
    "goal": "Retrieve all users",
    "attempt": {"method": "GET", "path": "/api/v1/users"},
    "observed": {"status": 200, "item_count": 100000},
    "missing_capability": "pagination",
    "suggestion": "Support cursor-based pagination",
    "agent": {"name": "example-agent", "version": "1.0.0"}
  }'
```

## Node.js package — example response

Success (`201 Created`):

```json
{
  "id": "fb_f5c7b3b91174cda3c401dc01",
  "status": "received"
}
```

Invalid payload (`400 Bad Request`):

```json
{
  "detail": "Invalid feedback payload.",
  "errors": [{ "path": "$.type", "message": "..." }]
}
```

Status codes follow SPEC §3.5: `201` received, `400` invalid feedback,
`401`/`403` when your `auth` middleware rejects, `429` if you add rate
limiting, `5xx` for server failures.

## Node.js package — storage

```ts
import { MemoryFeedbackStore, type FeedbackStore } from "feedback-protocol";
```

- `FeedbackStore` — interface with `save` / `get` / `list` / `count`.
  `save()` assigns the `fb_…` ID and the server-side UTC `received_at`
  timestamp, preserves a client-supplied `timestamp` when present, and
  returns a `StoredFeedback` record.
- `MemoryFeedbackStore` — non-persistent in-process implementation for
  development and tests.

Custom backends (PostgreSQL, Redis, external services) implement
`FeedbackStore` and are passed as `feedbackProtocol({ store })` — the
HTTP protocol does not change.

## Node.js package — production considerations

- **Authenticate** via the `auth` option (API key, OAuth2, …). The
  default middleware is open; unauthenticated public deployments will
  be spammed.
- **Rate-limit** with your gateway or Express rate-limiting middleware;
  return `429` with `Retry-After`.
- **Persist** with a durable `FeedbackStore` (single writer, bounded
  retention). Document what you store, how long, and who can access it
  (SPEC §5). Feedback is triage input — human review is required before
  any code change (SPEC §7).
- **Privacy.** Only `id` + `type` are logged (silence with
  `feedbackProtocol({ logger: false })`). Never log payloads, headers,
  cookies, or tokens.

## Complete architecture

```text
                  Agent
                    │
                    ▼
              Backend API
                    │
             problem encountered
                    │
                    ▼
        /.well-known/feedback-protocol
                    │
                    ▼
               /feedback
                    │
                    ▼
          Optional central server
                    │
                    ▼
             aggregation
                    │
                    ▼
                triage
                    │
                    ▼
          future investigation
                    │
                    ▼
             future PR agent
                    │
                    ▼
             human approval
```

Four layers, matching SPEC §1: the **protocol** (discovery +
submission, this is the contract), **SDK implementations** (Python,
TypeScript — they implement the protocol), the **agent skill**
(teaches agents when and how to report), and the **optional central
server** (storage, deterministic aggregation, human triage).

The central server is optional: a service can expose `/feedback`
directly via an SDK and never run it. Automatic code modification and
automatic merging are NOT part of the current project — the pipeline
ends at human triage, and any future investigation/PR stages end at
human approval.

## Central service — architecture (v0.5)

The central service turns individual reports into engineering signals:

```text
feedback → centralized storage → aggregation → human triage
```

- **Ingestion** (`POST /feedback`): accepts any protocol-compliant v0.1
  body plus an optional `service` identifier (string like `"users-api"`
  or object like `{"name": "users-api", "environment": "production"}`).
  Secrets are redacted before storage; unknown fields are preserved.
  Returns the standard `201 {"id", "status": "received"}` receipt, so
  existing SDK reporters work unchanged.
- **Storage** (SQLite via `service/db.py`): id, service identity,
  timestamp, type, agent info, goal, attempt, observed/expected behavior,
  metadata — never secrets. The store is a narrow abstraction
  (`save/get/list/set_status`), replaceable without touching HTTP.
- **Aggregation** (`GET /clusters`): deterministic, explainable grouping
  — same service + type + method + endpoint + missing capability ⇒ same
  cluster (stable `cluster_<hash>` id, count, first/last seen,
  representative report, member ids, status breakdown). No embeddings,
  no LLM.
- **Triage** (`PATCH /feedback/{id}`, `PATCH /clusters/{cluster_id}`):
  `new` → `investigating` → `accepted` / `rejected` → `resolved`.
  Reports start at `new` and are never auto-confirmed: `accepted` means
  a human verified a real problem.
- **Auth**: Bearer API key on everything except `/health` and protocol
  discovery. See `service/README.md` and "Production considerations"
  below for the full endpoint list.

v0.5 ends at triage. No PR generation, no repository changes, no merges.

## Central service — local setup

```bash
# 1. start server (SQLite, no cloud DB needed)
FEEDBACK_SERVICE_API_KEY=dev-key-change-me uvicorn --factory service.app:create_default_app --port 8001
#   …or: FEEDBACK_SERVICE_API_KEY=dev-key-change-me docker compose up --build  (port 8001)

# 2. submit feedback
curl -X POST localhost:8001/feedback -H "Authorization: Bearer dev-key-change-me" \
  -H 'Content-Type: application/json' \
  -d '{"service": "users-api", "type": "bug", "summary": "500 on project create"}'

# 3. inspect feedback
curl -H "Authorization: Bearer dev-key-change-me" localhost:8001/feedback?service=users-api

# 4. inspect clusters (try the A/B/C sample first: python service/seed_sample.py)
curl -H "Authorization: Bearer dev-key-change-me" localhost:8001/clusters

# 5. change triage status
curl -X PATCH -H "Authorization: Bearer dev-key-change-me" \
  -H 'Content-Type: application/json' -d '{"status": "investigating"}' \
  localhost:8001/feedback/fb_…
```

**Production considerations.** Change the default API key and keep it
secret; put the service behind your gateway/SSO for sensitive data.
Rate-limit ingestion (`429`). Back up the SQLite file (or swap
`SqliteFeedbackStore` for a managed backend — the HTTP layer does not
change). Document retention and access (SPEC §5). Secrets are redacted
at ingestion, but treat stored reports as internal data, not public.

## How v0.5 prepares feedback → investigation → PR

The next milestone can build repository investigation and PR generation
on top of v0.5 without new protocol work, because each stage already
produces the next stage's input: `accepted` clusters identify *what* to
fix (service + endpoint + evidence bundle via member reports);
`representative` + `feedback_ids` give an investigator the full
reproduction context; triage history (`investigating` → `accepted` →
`resolved`) provides the audit trail a PR description needs. v0.5
deliberately stops at human triage so automation later acts only on
human-confirmed signals.

## Agent skill — the reporting protocol for AI agents

`skill/SKILL.md` is the agent-facing side of the protocol: framework-agnostic
instructions (SKILL.md frontmatter format — compatible with OpenCode, Claude
Code, and other skill-capable agents) that teach an agent when to report,
when to stay silent, and how to write a report maintainers can act on. It is
the normative client-behavior companion to SPEC §4.

### The agent loop

1. **Goal** — state the user's goal in one sentence.
2. **Attempt** — accomplish it normally through the API, as documented.
3. **Classify** — on failure, place it in exactly one of eight categories:

| # | Category | Report? |
|---|----------|---------|
| 1 | Agent error (wrong endpoint, bad parameters, misread docs) | No — fix and retry |
| 2 | User/input error (invalid data or credentials) | No — tell the user |
| 3 | Expected behavior (validation error, documented quota) | No — handle it |
| 4 | Temporary failure (single 503/timeout, retry succeeds) | No — backoff + retry |
| 5 | API bug (documented endpoint violates its contract) | Yes — `bug` |
| 6 | Missing feature (works as documented, lacks a needed capability) | Yes — `missing_feature` |
| 7 | Documentation mismatch (docs contradict behavior) | Yes — `documentation` |
| 8 | Performance issue (persistent, measured, goal-blocking slowness) | Yes — `performance` |

Borderline rule: slowness coinciding with a missing capability is classified
by measurement — fast-but-incomplete is `missing_feature`; budget-breaching
is `performance`. A slow endpoint is measured at least 3 times before
reporting; a single slow response is category 4, not evidence.

4. **Recover** — fix its own mistakes, ask the user for correct input, retry
   transients with backoff. Only genuinely actionable, unrecoverable,
   service-side issues proceed.
5. **Discover** — `GET /.well-known/feedback-protocol` (falling back to
   explicit API docs only — never blind-probing `/feedback`).
6. **Evidence** — facts, never theories about internals: goal, attempt,
   observed, expected, measured timings. Investigation is read-only.
   Decisive facts live in the structured fields (`observed`, `expected`,
   `description`); the `summary` stands alone (endpoint + behavior +
   measurement). Reports never carry passwords, tokens, cookies, or
   personal data.
7. **Tell the user** — what was tried, what failed, the report id (`fb_…`)
   — reported, never fixed. If nothing was filed, one sentence saying why.

### Install and use

`skill/SKILL.md` is the source of truth — keep local installs in sync with
it. Copy it into the agent's skills directory (e.g.
`.opencode/skills/feedback-protocol/` for project scope,
`~/.config/opencode/skills/` for personal scope), or load it into context
as a system prompt / slash-command body before API work. It ships ten
worked examples: six where feedback is filed (500, documented-404, missing
pagination, documentation mismatch, unexpected truncation, slow endpoint)
and four where the agent must stay silent (bad credentials, the agent's own
invalid request, transient 503, out-of-scope feature request).

### Verified behavior

`evals/` grades real agent runs against 8 scenarios — bugs, missing
features, documentation mismatches, performance problems, plus negative
cases where silence is correct — scoring both the machine-readable
findings and the human-readable report. Currently 8/8 passing. See
[evals/README.md](evals/README.md).

---

## 1. What is it?

A tiny HTTP + JSON convention with two endpoints:

1. `GET /.well-known/feedback-protocol` — canonical discovery: whether a
   service accepts structured feedback reports and where to send them.
2. `POST /feedback` (or the advertised path) — submit a structured problem
   report (bug, missing feature, unexpected behavior, documentation
   mismatch, or performance problem).

No SDK, no database, no dashboard, no hosted service in the protocol
itself. Just a shared shape for reports so services can triage them.
(The Python package above is a reference implementation, not part of
the wire protocol.)

## 2. Why does it exist?

AI agents use APIs at machine speed. When they hit a genuine service-side
problem — a bug, a missing capability, wrong docs, or unusable latency —
that signal is usually lost: it ends up in a chat transcript, a retry loop,
or nowhere.

The Feedback Protocol gives that signal a structured home:

- Agents report **evidence, not speculation** (what they tried, what they
  observed, what they expected).
- Services get **machine-readable triage input** with minimal required
  fields (only `type` + `summary` are required).
- Both sides stay **language-independent** — plain HTTP and JSON.

It also protects services: agents MUST NOT file user errors, auth failures,
or their own mistakes as API bugs (see SPEC §4).

## 3. The basic workflow

```text
Agent
→ API request
→ failure/problem
→ investigate
→ discover feedback capability
→ POST /feedback
→ feedback ID
→ human/automation triage
```

In words:

1. The agent tries to accomplish the user's goal through the API.
2. It hits a failure or problem.
3. It investigates: re-reads docs, validates its own request, retries
   transient failures normally.
4. If the problem looks like a genuine service-side issue, it discovers
   the feedback capability (`GET /.well-known/feedback-protocol`).
5. It submits a structured report (`POST /feedback`).
6. It receives a receipt (`{"id": "fb_123", "status": "received"}`).
7. A human (or human-supervised automation) triages the report. Feedback
   never triggers code changes directly.

## 4. Discovery

Before submitting, the client discovers support:

```http
GET /.well-known/feedback-protocol HTTP/1.1
Host: api.example.com
```

Example response:

```json
{
  "version": "0.1",
  "feedback_endpoint": "/feedback",
  "methods": ["POST"]
}
```

Rules (see SPEC §2 for normative text):

- Discover first; do not guess the submission URL.
- If discovery is unavailable, clients MUST NOT assume `/feedback` exists.
- Clients MAY fall back to explicitly documented protocol information in
  the service's API docs.
- Arbitrary path probing (trying `/feedback`, `/api/feedback`, …) is
  forbidden.

## 5. Feedback submission

```http
POST /feedback HTTP/1.1
Host: api.example.com
Content-Type: application/json
```

The body MUST conform to `schema/feedback.schema.json`. Only `type` and
`summary` are required; everything else is optional evidence.

Supported `type` values in v0.1: `bug`, `missing_feature`,
`unexpected_behavior`, `documentation`, `performance`.

## 6. Example request

Reporting a missing pagination capability:

```json
{
  "type": "missing_feature",
  "summary": "Users endpoint does not support pagination",
  "goal": "Retrieve all users",
  "attempt": {
    "method": "GET",
    "path": "/api/v1/users"
  },
  "observed": {
    "status": 200,
    "item_count": 100000
  },
  "missing_capability": "pagination",
  "suggestion": "Support cursor-based pagination",
  "agent": {
    "name": "example-agent",
    "version": "1.0.0"
  }
}
```

## 7. Example response

Minimal successful response:

```json
{
  "id": "fb_123",
  "status": "received"
}
```

Servers SHOULD return `201 Created` (or `200 OK`; `202 Accepted` if
triage is asynchronous). Errors use standard codes: `400` invalid
feedback, `401`/`403` unauthorized, `429` rate limited, `5xx` server
error. See SPEC §3.5.

## 8. Current scope (v0.1 protocol / v0.2–v0.5 implementations)

Protocol:

- Discovery endpoint (`GET /.well-known/feedback-protocol`).
- Submission endpoint (`POST` to the advertised path).
- Stable JSON Schema with 5 feedback types and 16 top-level fields
  (2 required, 14 optional — additive under SPEC §9: `service`,
  `session_id`, `trace_id`, and structured `expected` joined later
  without breaking v0.1 reporters).
- Reporting semantics (what counts as feedback vs. agent/user error).
- Response receipt shape + HTTP status code guidance.
- Design principles: language independence, machine readability, evidence
  over speculation, minimal required information, privacy, authentication,
  rate limiting, idempotency, extensibility, human review before code
  changes.

v0.2 Python package (this repo):

- `feedback-protocol` distribution with `feedback_protocol.fastapi`
  router, Pydantic models mirroring the schema, `FeedbackStore` +
  `InMemoryFeedbackStore`, `fb_…` ID generation, server-side UTC
  timestamps, `400`-normalized validation, tests, and a runnable
  `examples/fastapi/` service.

v0.3 agent skill (this repo):

- `skill/SKILL.md`: framework-agnostic instructions teaching agents when
  and how to report, with ten worked examples.

v0.4 Node.js package (this repo):

- `feedback-protocol` npm distribution with `feedbackProtocol()`
  Express middleware, strict TypeScript types mirroring the schema,
  `FeedbackStore` + `MemoryFeedbackStore`, `fb_…` ID generation,
  server-side UTC timestamps, schema-compatible validation, tests, and
  a runnable `examples/express/` service.
- Implements the same v0.1 protocol as the Python package — no
  Node-specific protocol (see the parity note at the top).

v0.5 central service (this repo):

- `service/` FastAPI app with SQLite storage: protocol-compliant
  ingestion (+ optional `service` identity), secret redaction, filtered
  retrieval, deterministic clusters, and human triage statuses.
- `docker-compose.yml` + `service/Dockerfile` for local development;
  `service/seed_sample.py` demonstrates the A/B/C single-cluster case.
- Stops at triage: no PR generation, no repository changes, no merges.

## 9. What is intentionally NOT included

- Centralized feedback aggregation, dashboards.
- Automatic issue creation, PR generation, or autonomous code changes.
- Client libraries beyond the Python and Node.js reference implementations.
- Databases, storage schemas, or hosted services (beyond the
  `FeedbackStore` extension interfaces).
- Triage processes, SLAs, or prioritization rules.
- Spam/reputation scoring.
- Authentication mechanism mandates (servers define and document their own).
- New feedback types or required fields beyond the v0.1 set.

## 10. Roadmap

Possible directions after v0.5 (not commitments):

- Richer `attempt`/`observed` evidence conventions, additional examples
  per feedback type; optional `Idempotency-Key` semantics.
- Reference triage queue schema (still no hosted service).
- `v1.0`: stability guarantees, version-negotiation rules, multilingual
  summary guidance.
- Later: opt-in webhooks for receipt status, community SDKs, spam-control
  recommendations.

Contributions that keep the protocol simple are welcome. Proposals that
add required fields, new endpoints, or automation without human review
need strong justification.

## License

MIT — see [LICENSE](LICENSE).
