---
name: feedback-protocol
description: Report genuine API bugs, missing capabilities, documentation mismatches, and performance problems to services using the Feedback Protocol. Use when an API behaves incorrectly, lacks a needed capability, contradicts its docs, or is unusably slow — after ruling out your own errors, bad user input, and transient failures.
---

# Feedback Protocol — Agent Skill

You interact with backend APIs on behalf of a user. When an API itself is
the problem — a bug, a missing capability, wrong documentation, or
unusable performance — you can file a structured report with the service
so its maintainers can fix it. This skill tells you when to report, when
to stay silent, and how to write a good report.

Protocol reference (normative, read when in doubt):

- `SPEC.md` — full specification.
- `schema/feedback.schema.json` — the exact JSON shape. Only `type` and
  `summary` are required; everything else is optional evidence.

## The process

Follow these steps in order:

1. **Understand the user's goal.** What outcome does the user actually
   want? Write it down in one sentence. You will need it for the report.
2. **Attempt to accomplish the goal normally.** Use the API as documented.
3. **If the operation fails, determine why.** Read the status code, the
   error body, and the relevant documentation before concluding anything.
4. **Classify the failure** using the eight categories below.
5. **Attempt reasonable recovery when appropriate.** Fix your own request,
   ask the user for correct input, or retry transient failures with
   backoff. Do not report problems you can resolve yourself.
6. **If the issue is genuinely actionable and the service supports the
   Feedback Protocol:** discover the protocol, collect evidence, and
   submit structured feedback.
7. **Tell the user what happened** — what you tried, what failed, whether
   you reported it, and what happens next.

## Classifying a failure

Classify every failure into exactly one category before deciding anything:

| # | Category | Meaning | Report? |
|---|----------|---------|---------|
| 1 | Agent error | *You* made the mistake: wrong endpoint, bad parameters, misread docs. | No — fix your request. |
| 2 | User/input error | The user's data or credentials are invalid. | No — tell the user. |
| 3 | Expected API behavior | The API correctly rejected or limited the request per its contract (validation error, documented quota). | No — handle it. |
| 4 | Temporary failure | A transient error (single 503/timeout) that succeeds after normal retries. | No — retry with backoff. |
| 5 | API bug | A documented endpoint violates its own contract. | **Yes — `type: "bug"`.** |
| 6 | Missing feature | The API works as documented but lacks a capability needed for a legitimate goal. | **Yes — `type: "missing_feature"`.** |
| 7 | Documentation mismatch | The docs and the behavior disagree, or the docs are absent where they should exist. | **Yes — `type: "documentation"`** (or `"unexpected_behavior"` if you genuinely cannot tell docs from bug but have concrete evidence of surprise). |
| 8 | Performance issue | Latency/throughput makes the API unusable for a legitimate goal, after normal retries. | **Yes — `type: "performance"`.** |

When unsure whether the fault is yours, investigate first: re-read the
docs, validate your request parameters, and retry once. If the fault is
still unexplained after that, treat it as category 5 or 7 — with evidence,
not a theory about the cause.

## Recovery before reporting

- **Agent error:** correct the request and retry. Never report your own
  mistakes.
- **User/input error:** explain the problem to the user and ask for
  corrected input. Never report their typos or bad credentials as API bugs.
- **Expected behavior:** handle it in your workflow (e.g. respect the
  quota, surface the validation message).
- **Temporary failure:** retry with exponential backoff and jitter. Report
  nothing if a retry succeeds. Only escalate to `performance` if failures
  persist and block the goal.

## Discovery

Never assume a service accepts feedback. Discover support first:

1. Send `GET /.well-known/feedback-protocol`.
2. A `200` response advertises the protocol, e.g.:
   ```json
   {
     "version": "0.1",
     "feedback_endpoint": "/feedback",
     "methods": ["POST"]
   }
   ```
   Submit to the advertised `feedback_endpoint` (commonly `/feedback`).
3. If discovery is unavailable (non-2xx, network error, invalid body),
   you MUST NOT assume `/feedback` exists. You MAY use explicitly
   documented protocol information from the service's API documentation.
4. You MUST NOT blindly `POST` to `/feedback` (or any guessed path) on
   arbitrary services. No discovery and no docs means no report.

## Collecting evidence

A good report contains facts. Collect these fields when available:

- `goal` — the user's goal in one sentence.
- `attempt.method` / `attempt.path` — the endpoint and HTTP method tried.
- `observed` — what actually happened: HTTP `status`, error codes or
  messages returned, counts, timings, retry counts. Facts only.
- `expected` — what the docs (or reasonable convention) led you to
  expect. Quote the docs when relevant.
- `missing_capability` — for missing features: the absent capability
  in a few words (e.g. `"pagination"`).
- `suggestion` — a non-binding hint (e.g. `"Support cursor-based
  pagination"`). Never a directive; you do not know the internals.
- `request_id` — the service's correlation ID, if it provided one.
- `session_id` / `trace_id` — your interaction or trace identifiers, when
  available. They let maintainers join the report back to logs.
- `service` — which service had the problem: a plain name
  (`"payments-api"`) or `{name, version, environment}`. Send what you
  know; every sub-field is optional.
- `expected` — a short statement, or a small structure for capability
  expectations (e.g. `{"capability": "pagination"}`). Never a root-cause
  claim: you report evidence, maintainers determine causes.
- Timing evidence for slowness goes in `observed` (durations, retry
  counts) — never full request/response bodies.
- `agent.name` / `agent.version` — your own identity.

Distinguish **evidence** (what you saw) from **speculation** (why you
think it happens). Report the former; never invent the latter.

Bad (speculation about internals):

> "The backend has a database bug."

Good (observed facts):

> "`POST /api/v1/authentication` returned HTTP 500 with request ID
> `req_123`."

Only `type` and `summary` are required — file the report even when some
evidence is unavailable rather than guessing to fill fields.

## Submission

- `POST` the JSON report to the advertised endpoint with
  `Content-Type: application/json`.
- A `201` (or `200`) response with `{"id": "...", "status": "received"}`
  means the report was recorded. Keep the `id` for the user.
- A `400` means your report is malformed — fix it. A `401`/`403` means
  the endpoint requires credentials you do not have — stop and tell the
  user. A `429` means back off and retry later.

## Examples

### 1. Existing endpoint returns 500 → report (`bug`)

- **User request:** "Create a project called Atlas."
- **Agent action:** `POST /api/v1/projects` with `{"name": "Atlas"}` (all
  required fields per the docs; request validated twice).
- **API result:** HTTP 500, body `{"error": "internal_error",
  "request_id": "req_123"}`. Reproduced on retry with identical input.
- **Agent reasoning:** Documented endpoint, valid request, persistent 500
  → category 5 (API bug). Recovery impossible; nothing wrong with the
  input.
- **Feedback submitted:** yes.
  ```json
  {
    "type": "bug",
    "summary": "POST /api/v1/projects returns 500 for a valid request",
    "goal": "Create a project called Atlas",
    "attempt": {"method": "POST", "path": "/api/v1/projects"},
    "observed": {"status": 500, "error": "internal_error"},
    "expected": "201 with the created project, per the API docs",
    "request_id": "req_123",
    "agent": {"name": "example-agent", "version": "1.0.0"}
  }
  ```

### 2. Documented endpoint returns 404 → report (`bug`)

- **User request:** "Show me organization acme."
- **Agent action:** `GET /api/v1/organizations/acme`, an endpoint listed
  in the current docs.
- **API result:** HTTP 404 `{"error": "not_found"}` for an organization
  that exists and is visible in the dashboard.
- **Agent reasoning:** Docs say the endpoint exists; a valid resource
  returns 404 → category 5 (API bug). Re-checked the path spelling and
  the organization slug before concluding.
- **Feedback submitted:** yes.
  ```json
  {
    "type": "bug",
    "summary": "GET /api/v1/organizations/{slug} returns 404 for existing organization",
    "goal": "Show the acme organization",
    "attempt": {"method": "GET", "path": "/api/v1/organizations/acme"},
    "observed": {"status": 404, "error": "not_found"},
    "expected": "200 with the organization, per the API docs",
    "agent": {"name": "example-agent", "version": "1.0.0"}
  }
  ```

### 3. Missing pagination → report (`missing_feature`)

- **User request:** "Export all users."
- **Agent action:** `GET /api/v1/users` as documented.
- **API result:** HTTP 200 with a single 100,000-item array and no
  pagination parameters documented or honored (`?page=2` returns the same
  array).
- **Agent reasoning:** The endpoint works as documented but cannot serve
  the legitimate goal safely → category 6 (missing feature). The agent
  does not know the internal cause and does not claim one.
- **Feedback submitted:** yes.
  ```json
  {
    "type": "missing_feature",
    "summary": "Users endpoint does not support pagination",
    "goal": "Retrieve all users",
    "attempt": {"method": "GET", "path": "/api/v1/users"},
    "observed": {"status": 200, "item_count": 100000},
    "missing_capability": "pagination",
    "suggestion": "Support cursor-based pagination",
    "agent": {"name": "example-agent", "version": "1.0.0"}
  }
  ```

### 4. Documentation mismatch → report (`documentation`)

- **User request:** "Filter orders by status."
- **Agent action:** `GET /api/v1/orders?status=paid`, exactly as the docs
  describe.
- **API result:** HTTP 400 `{"error": "unknown_query_param: status"}`.
- **Agent reasoning:** Docs and behavior contradict each other →
  category 7 (documentation mismatch). The agent quotes the docs in
  `expected` and the behavior in `observed` without deciding which side
  is wrong.
- **Feedback submitted:** yes.
  ```json
  {
    "type": "documentation",
    "summary": "Docs describe ?status filter that the API rejects",
    "goal": "Filter orders by status",
    "attempt": {"method": "GET", "path": "/api/v1/orders"},
    "observed": {"status": 400, "error": "unknown_query_param: status"},
    "expected": "Docs list ?status=paid as a supported filter",
    "agent": {"name": "example-agent", "version": "1.0.0"}
  }
  ```

### 5. Unexpected response → report (`unexpected_behavior`)

- **User request:** "List the first 50 invoices."
- **Agent action:** `GET /api/v1/invoices?limit=50`, a documented
  parameter.
- **API result:** HTTP 200 with only 10 items, no error, no paging token,
  no explanation.
- **Agent reasoning:** Neither a clear bug nor a documented behavior —
  silently truncated results → `unexpected_behavior`, with the observed
  facts attached.
- **Feedback submitted:** yes.
  ```json
  {
    "type": "unexpected_behavior",
    "summary": "?limit=50 silently returns only 10 invoices",
    "goal": "List the first 50 invoices",
    "attempt": {"method": "GET", "path": "/api/v1/invoices"},
    "observed": {"status": 200, "requested_limit": 50, "returned_count": 10},
    "expected": "50 invoices or a paging token, per the docs",
    "agent": {"name": "example-agent", "version": "1.0.0"}
  }
  ```

### 6. Slow endpoint → report (`performance`)

- **User request:** "Check the status of deployment d-9."
- **Agent action:** `GET /api/v1/deployments/d-9`, retried 3 times with
  exponential backoff.
- **API result:** All attempts take 45–60s then return 200; the docs
  promise p99 under 2s for this endpoint.
- **Agent reasoning:** Persistent, goal-blocking slowness after normal
  retries → category 8 (performance issue). Timing evidence included;
  no user data included.
- **Feedback submitted:** yes.
  ```json
  {
    "type": "performance",
    "summary": "GET deployment status takes 45-60s, docs promise p99 under 2s",
    "goal": "Check the status of deployment d-9",
    "attempt": {"method": "GET", "path": "/api/v1/deployments/d-9"},
    "observed": {"status": 200, "durations_s": [48, 55, 60], "retries": 3},
    "expected": "p99 under 2s per the API docs",
    "agent": {"name": "example-agent", "version": "1.0.0"}
  }
  ```

### 7. Invalid user credentials → no report

- **User request:** "Show my billing."
- **Agent action:** `GET /api/v1/billing` with the user's API key.
- **API result:** HTTP 401 `{"error": "invalid_api_key"}`.
- **Agent reasoning:** Category 2 (user/input error). The credential is
  wrong, expired, or revoked — an ordinary authentication failure, not
  an API bug.
- **Feedback submitted:** no. Tell the user their key was rejected and
  ask for a valid one.

### 8. Agent constructed an invalid request → no report

- **User request:** "Create a task."
- **Agent action:** `POST /api/v1/tasks` with `{"title": 42}` (a number
  where the docs require a string).
- **API result:** HTTP 422 `{"error": "title must be a string"}`.
- **Agent reasoning:** Category 1 (agent error). The docs are clear; the
  request was malformed by the agent.
- **Feedback submitted:** no. Fix the request (`{"title": "42"}`) and
  retry.

### 9. Temporary 503 → no report

- **User request:** "Get the current weather."
- **Agent action:** `GET /api/v1/weather?city=berlin`.
- **API result:** HTTP 503 on the first attempt; a retry after backoff
  returns 200 with correct data.
- **Agent reasoning:** Category 4 (temporary failure) that resolved
  through normal retry behavior.
- **Feedback submitted:** no. Transient failures are expected in
  distributed systems; reporting each one would be noise.

### 10. Feature genuinely does not exist → no report

- **User request:** "Send a fax through the API."
- **Agent action:** Checked the docs for fax endpoints; searched the API
  reference.
- **API result:** No fax capability is documented or advertised anywhere.
- **Agent reasoning:** This is an unsupported request clearly outside the
  API's documented capabilities — not a missing capability encountered
  during legitimate use of the API's domain (contrast with example 3,
  where pagination was needed to use the documented users endpoint
  itself). Filing "please build a fax service" is a feature request,
  not actionable protocol feedback.
- **Feedback submitted:** no. Tell the user the API does not offer this.

## Rules

You MUST NOT report:

- Ordinary authentication failures (wrong/expired user credentials).
- Invalid user input.
- Mistakes caused by you (bad parameters, wrong endpoints, misread docs).
- Expected API errors (validation messages, documented quotas and limits).
- Unsupported requests clearly outside the API's documented capabilities.
- Every transient failure — only persistent, goal-blocking problems after
  normal retries.

You SHOULD report:

- Documented endpoints behaving incorrectly (reproducible bugs).
- Genuine missing capabilities encountered during legitimate work.
- Documentation mismatches (docs contradict behavior, or docs are absent).
- Significant performance problems (persistent, measured, goal-blocking).

## Telling the user

After submitting, never claim the problem is fixed. Filing a report only
records the issue for the service maintainers. Use this shape:

> "I ran into [one-sentence problem] while [goal]. I've reported it to
> the service (report `fb_…`) so their team can look into it. It is not
> fixed yet. Meanwhile, [workaround or next step]."

If you did not report, say why in one sentence ("Your API key was
rejected, so I didn't file a bug report — the credential needs fixing
first.").

## Safety

NEVER include in feedback:

- Passwords, API keys, or access tokens.
- Cookies or `Authorization` headers (or any credential material).
- Session tokens or private keys.
- Personal data beyond the minimum needed to reproduce the issue.

Redact aggressively: prefer synthetic or truncated examples over real
user data. When in doubt, omit the field — only `type` and `summary`
are required. If a service requires secrets in order to file feedback,
do not comply; tell the user instead.
