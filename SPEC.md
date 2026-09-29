# Feedback Protocol — Specification v0.1

Status: Draft (v0.1)

This document is the normative specification for the Feedback Protocol.
It is intended to be understandable to a backend developer who has never
heard of the project.

## 1. Overview

The Feedback Protocol is a language-independent convention that lets
AI agents report actionable problems they encounter while using backend APIs.

The core idea:

> An agent attempts to accomplish a user's goal through an API. If it
> encounters a genuine bug, missing capability, unexpected behavior,
> documentation mismatch, or performance problem, it can submit structured
> feedback to the service.

The protocol defines only two things:

1. A discovery endpoint to advertise feedback support.
2. A submission endpoint that accepts a stable JSON schema.

It does NOT define storage, dashboards, triage automation, code generation,
SDKs, or hosted services. See [README.md](README.md) for out-of-scope items.

### 1.1 Conformance language

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT",
"SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" are to be
interpreted as described in RFC 2119 / RFC 8174.

### 1.2 Versioning

The current protocol version is `0.1`.

- The `version` string in the discovery document identifies the protocol
  version supported by the server.
- Minor clarifications that do not break existing clients or servers keep
  the same version.
- Any breaking change to the discovery document or feedback schema
  REQUIRES a new protocol version.

## 2. Discovery

A service advertises support for the protocol at a well-known URI:

```http
GET /.well-known/feedback-protocol
```

### 2.1 Discovery request

- Method: `GET`
- Path: exactly `/.well-known/feedback-protocol`
- The request has no body and defines no query parameters in v0.1.

### 2.2 Discovery response

On success the server MUST return HTTP `200` with a JSON object containing:

| Field             | Type     | Required | Description                                              |
| ----------------- | -------- | -------- | -------------------------------------------------------- |
| `version`         | string   | Yes      | Protocol version supported, e.g. `"0.1"`.                |
| `feedback_endpoint` | string | Yes      | Path where feedback is accepted, e.g. `"/feedback"`.     |
| `methods`         | string[] | Yes      | HTTP methods accepted at that endpoint. v0.1: `["POST"]`. |

Example:

```json
{
  "version": "0.1",
  "feedback_endpoint": "/feedback",
  "methods": ["POST"]
}
```

Servers MAY include additional informational fields. Clients MUST ignore
fields they do not understand.

### 2.3 Discovery rules

- Clients SHOULD first discover the protocol via
  `GET /.well-known/feedback-protocol` before submitting feedback.
- If the discovery endpoint is unavailable (non-2xx, network error, or
  invalid body), clients MUST NOT assume that `/feedback` exists.
- In that case clients MAY use explicitly documented protocol information
  from the service's API documentation (e.g. a documented custom feedback
  URL). Documentation takes precedence over guessing.
- Clients MUST NOT probe arbitrary paths (such as trying `/feedback`,
  `/api/feedback`, etc.) when discovery fails. Arbitrary probing is
  undefined behavior and MUST NOT be implemented.

## 3. Feedback submission

### 3.1 Submission request

- Method: `POST`
- Path: the `feedback_endpoint` advertised in the discovery document
  (commonly `/feedback`).
- `Content-Type` MUST be `application/json`.
- The request body MUST be a JSON object conforming to
  [`schema/feedback.schema.json`](schema/feedback.schema.json).

### 3.2 Feedback schema

The schema file is normative. What follows is a human-readable summary.
In case of conflict, the JSON Schema file wins.

Only `type` and `summary` are REQUIRED. All other fields are OPTIONAL.
This is intentional: an agent must be able to report a missing feature
without knowing the internal cause, and must not be forced to speculate.

| Field                | Type   | Required | Applies to | Description |
| -------------------- | ------ | -------- | ---------- | ----------- |
| `type`               | string | Yes      | all        | One of `bug`, `missing_feature`, `unexpected_behavior`, `documentation`, `performance`. |
| `summary`            | string | Yes      | all        | Short (1–280 char) human-readable summary. |
| `description`        | string | No       | all        | Longer context the summary cannot carry. |
| `goal`               | string | No       | all        | What the agent was trying to accomplish for the user. |
| `attempt`            | object | No       | all        | The operation attempted. May contain `method` (e.g. `"GET"`) and `path` (e.g. `"/api/v1/users"`). Additional evidence fields are allowed. |
| `observed`           | object | No       | all        | What was actually observed (facts). May contain `status` (HTTP status code) plus any other evidence. |
| `expected`           | string | No       | all        | What was expected from docs or reasonable conventions. |
| `missing_capability` | string | No       | `missing_feature` (typical) | The absent capability, e.g. `"pagination"`. |
| `suggestion`         | string | No       | all        | Non-binding suggestion, e.g. `"Support cursor-based pagination"`. Hints only. |
| `agent`              | object | No       | all        | Reporter identity: `name` (required if `agent` present), `version` (optional). |
| `request_id`         | string | No       | all        | Correlation ID of the triggering request, if provided by the service. |
| `timestamp`          | string | No       | all        | RFC 3339 date-time (UTC) when observed, e.g. `"2026-01-15T12:34:56Z"`. |
| `metadata`           | object | No       | all        | Extra machine-readable context. MUST NOT contain secrets or personal data. |

Top-level and nested objects allow additional properties for forward
compatibility. Clients and servers MUST ignore fields they do not
understand (see §7 Extensibility).

#### Feedback types

- `bug`: The API behaves incorrectly relative to its own contract
  (e.g. 500 on a documented valid call, corrupt data).
- `missing_feature`: The API works as documented but lacks a capability
  needed to complete a legitimate goal (e.g. no pagination).
- `unexpected_behavior`: The API behaves in a surprising way that is not
  clearly a bug or documented behavior (e.g. silently truncates results).
- `documentation`: Docs are wrong, incomplete, or contradict observed
  behavior. `expected` SHOULD cite what the docs said; `observed` SHOULD
  cite what happened.
- `performance`: Latency, throughput, or resource behavior makes the API
  unusable or unreliable for a legitimate goal (after normal retries).

### 3.3 Complete example

The following example MUST validate against the schema:

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

### 3.4 Submission response

On success the server MUST return a JSON object with at least:

```json
{
  "id": "fb_123",
  "status": "received"
}
```

| Field    | Type   | Required | Description |
| -------- | ------ | -------- | ----------- |
| `id`     | string | Yes      | Opaque server-assigned feedback identifier. Format is server-defined. |
| `status` | string | Yes      | Receipt status. v0.1 defines `"received"`. |

Servers MAY include additional fields (e.g. a `uri` for tracking).
Clients MUST ignore unknown fields.

### 3.5 HTTP status codes

Servers SHOULD use the following status codes:

| Situation | Code | Notes |
| --------- | ---- | ----- |
| Successful submission | `201 Created` (RECOMMENDED) or `200 OK` | Return the receipt object in the body. `202 Accepted` MAY be used if triage is asynchronous but the report has been durably accepted. |
| Invalid feedback | `400 Bad Request` | Body does not parse as JSON or fails schema validation. The response SHOULD include a machine-readable error describing the problem. |
| Unauthorized submission | `401 Unauthorized` or `403 Forbidden` | `401` when authentication is missing/invalid; `403` when authenticated but not permitted to submit feedback. |
| Rate limiting | `429 Too Many Requests` | Client is sending too much feedback. Respect `Retry-After` if present. |
| Server error | `5xx` | `500 Internal Server Error` (or `502`/`503` as appropriate) for transient or persistent server failures. Clients MAY retry with backoff; see §6. |

## 4. Reporting semantics — what counts as feedback

### 4.1 Agents MUST NOT report ordinary user errors as API bugs

The following normally MUST NOT generate feedback:

- Invalid credentials (wrong API key, expired token supplied by the user).
- Malformed requests caused by the agent itself (bad JSON, wrong types,
  missing required parameters the docs clearly specify).
- Unsupported requests caused by misunderstanding the API (calling an
  endpoint that does not exist, using a feature the docs say is unsupported).
- Temporary failures that resolve through normal retry behavior
  (single 503/timeout followed by success with exponential backoff).

If the agent is unsure whether the fault is its own, it MUST investigate
(re-read docs, validate its request, retry per §6) before submitting.

### 4.2 Seven-way distinction

Before submitting, the agent SHOULD classify the situation as one of:

1. **Agent error** — the agent made a mistake (bad parameters, wrong
   endpoint, misread docs). Action: fix the request, do NOT submit feedback.
2. **User/input error** — the user's data or instructions are invalid
   (bad credentials, impossible request). Action: ask the user / report
   back to the user, do NOT submit feedback.
3. **Expected API behavior** — the API correctly rejected or limited the
   request per its contract (validation error, documented quota).
   Action: handle it, do NOT submit feedback.
4. **API bug** — use `type: "bug"`. The API violates its own contract.
   Action: submit feedback with `attempt`, `observed`, and `expected`.
5. **Missing API capability** — use `type: "missing_feature"`. The API
   works as documented but cannot achieve a legitimate goal.
   Action: submit feedback with `goal`, `attempt`, `missing_capability`,
   and optionally `suggestion`.
6. **Documentation mismatch** — use `type: "documentation"`. Docs and
   behavior disagree and it is unclear which is wrong, or docs are absent.
   Action: submit feedback quoting docs in `expected` and behavior in
   `observed`.
7. **Performance problem** — use `type: "performance"`. Only after normal
   retries and when the behavior blocks a legitimate goal.
   Action: submit feedback with timing evidence in `observed`/`metadata`
   (e.g. durations, retry counts), never with user data.

Types `unexpected_behavior` is appropriate when the agent cannot cleanly
decide between 4 and 6 but has concrete evidence of surprise; it MUST still
provide `observed` evidence.

## 5. Privacy

- Feedback MUST NOT contain secrets: API keys, tokens, passwords,
  `Authorization` headers, session cookies, or private keys.
- Feedback MUST NOT contain personal data beyond what is strictly needed
  to reproduce the issue. Prefer redacted or synthetic examples.
- `attempt` bodies, `observed` payloads, and `metadata` MUST be redacted
  or minimized before submission. When in doubt, omit.
- Servers MUST document what they store, how long they retain feedback,
  and who can access it.
- Servers MUST NOT require agents to submit secrets or personal data in
  order to file feedback.

## 6. Authentication, rate limiting, idempotency

### Authentication

- The protocol does not mandate a single auth mechanism (language
  independence). Servers define their own (e.g. API key, OAuth 2.0, none
  for public betas) and MUST document it.
- If auth is required, unauthenticated requests MUST receive `401`, and
  unauthorized ones `403`.
- Anonymous feedback MAY be allowed; servers SHOULD note the trade-off
  (lower friction vs. spam).

### Rate limiting

- Servers SHOULD rate-limit feedback submission to prevent spam and loops
  (agents reporting about reporting).
- On `429` the server SHOULD include a `Retry-After` header.
- Clients MUST back off on `429` and `5xx` (exponential backoff with jitter
  is RECOMMENDED) and MUST NOT retry `400`, `401`, or `403` without fixing
  the underlying problem.

### Idempotency

- Clients SHOULD deduplicate before submitting (do not file the same
  observation twice for the same `request_id` / goal).
- Clients MAY send an `Idempotency-Key` header with `POST /feedback`.
  Servers that support it MUST document the behavior (e.g. same key within
  24h returns the original receipt).
- Servers MAY deduplicate on their side but MUST still return a valid
  receipt object.

## 7. Design principles

- **Language independence.** The protocol is plain HTTP + JSON. No SDK,
  no language-specific types, no code generation required.
- **Machine readability.** Stable JSON Schema, well-known discovery,
  predictable status codes. Human text (`summary`, `description`) is for
  triage; structured fields (`type`, `attempt`, `observed`) are for machines.
- **Evidence over speculation.** Prefer `observed` facts (status codes,
  counts, timings) to theories. `suggestion` is always a hint, never a
  directive. Agents MUST NOT invent internal causes.
- **Minimal required information.** Only `type` and `summary` are required
  so a report is never blocked on unknown internals.
- **Privacy.** Omit secrets and personal data by default; redact aggressively.
- **Authentication.** Defined by the server, documented clearly, enforced
  with standard codes.
- **Rate limiting.** Expected on both sides; backoff is mandatory behavior
  for well-behaved clients.
- **Idempotency.** Deduplication keys and client-side restraint prevent
  feedback storms.
- **Extensibility.** Unknown fields MUST be ignored. New optional fields
  and new `type` values MAY be added in future versions without breaking
  v0.1 clients; new required fields REQUIRE a version bump.
- **Human review before code changes.** Feedback is input to triage, not
  an instruction to change code. No server or automation SHOULD apply code
  or config changes solely on the basis of an agent report. A human (or
  explicitly authorized human-supervised automation) MUST review first.

## 8. Out of scope for v0.1

v0.1 intentionally does not define: SDKs, client libraries, persistent
storage schemas, dashboards, notification/webhook formats, SLA or triage
processes, reputation/spam scoring, or autonomous code-fix behavior.

## Appendix A. Minimal exchange

Discovery:

```http
GET /.well-known/feedback-protocol HTTP/1.1
Host: api.example.com
```

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "version": "0.1",
  "feedback_endpoint": "/feedback",
  "methods": ["POST"]
}
```

Submission:

```http
POST /feedback HTTP/1.1
Host: api.example.com
Content-Type: application/json
```

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

Receipt:

```http
HTTP/1.1 201 Created
Content-Type: application/json

{
  "id": "fb_123",
  "status": "received"
}
```
