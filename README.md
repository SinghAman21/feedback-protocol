# Feedback Protocol

An open, language-independent protocol that lets AI agents report actionable
problems they encounter while using backend APIs.

Version: **0.1** — protocol and specification only.

Normative documents:

- [SPEC.md](SPEC.md) — the full specification (normative).
- [schema/feedback.schema.json](schema/feedback.schema.json) — the stable JSON Schema (normative).

## 1. What is it?

A tiny HTTP + JSON convention with two endpoints:

1. `GET /.well-known/feedback-protocol` — discover whether a service accepts
   agent feedback and where to send it.
2. `POST /feedback` (or the advertised path) — submit a structured problem
   report (bug, missing feature, unexpected behavior, documentation
   mismatch, or performance problem).

No SDK, no database, no dashboard, no hosted service. Just a shared shape
for reports so services can triage them.

## 2. Why does it exist?

AI agents use APIs at machine speed. When they hit a genuine service-side
problem — a bug, a missing capability, wrong docs, or unusable latency —
that signal is usually lost: it ends up in a chat transcript, a retry loop,
or nowhere.

The Agent Feedback Protocol gives that signal a structured home:

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

## 8. Current scope (v0.1)

- Discovery endpoint (`GET /.well-known/feedback-protocol`).
- Submission endpoint (`POST` to the advertised path).
- Stable JSON Schema with 5 feedback types and 12 top-level fields
  (2 required, 10 optional).
- Reporting semantics (what counts as feedback vs. agent/user error).
- Response receipt shape + HTTP status code guidance.
- Design principles: language independence, machine readability, evidence
  over speculation, minimal required information, privacy, authentication,
  rate limiting, idempotency, extensibility, human review before code
  changes.

## 9. What is intentionally NOT included in v0.1

- SDKs or client libraries (any language).
- Databases, storage schemas, or hosted services.
- Dashboards, notifications, or webhook formats.
- Triage processes, SLAs, or prioritization rules.
- Spam/reputation scoring.
- Autonomous PR agents or automatic code fixes.
- Authentication mechanism mandates (servers define and document their own).
- New feedback types or required fields beyond the v0.1 set.

If you are looking for any of these, v0.1 is deliberately not the place —
open an issue to discuss a future version.

## 10. Roadmap

Possible directions after v0.1 (not commitments):

- `v0.2`: optional `Idempotency-Key` semantics, richer `attempt`/`observed`
  evidence conventions, additional examples per feedback type.
- `v0.3`: reference server validator + example triage queue schema
  (still no hosted service).
- `v1.0`: stability guarantees, version-negotiation rules, multilingual
  summary guidance.
- Later: opt-in webhooks for receipt status, community SDKs, spam-control
  recommendations.

Contributions that keep the protocol simple are welcome. Proposals that
add required fields, new endpoints, or automation without human review
need strong justification.

## License

MIT — see [LICENSE](LICENSE).
