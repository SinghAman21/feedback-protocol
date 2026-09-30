# Central feedback service (v0.5)

Receives protocol-compliant feedback, stores it in SQLite, groups it
into deterministic clusters, and tracks human triage.

Pipeline: feedback → centralized storage → aggregation → human triage.
No PR generation, no repository changes — that is a future milestone.

## Quickstart (local, no Docker)

```bash
pip install fastapi "uvicorn[standard]" -e .
export FEEDBACK_SERVICE_API_KEY=dev-key-change-me  # change in production
uvicorn --factory service.app:create_default_app --port 8001
```

## Quickstart (Docker)

```bash
FEEDBACK_SERVICE_API_KEY=dev-key-change-me docker compose up --build
```

Then, with `KEY=dev-key-change-me` and `BASE=http://localhost:8001`:

1. **Submit feedback:**
   ```bash
   curl -X POST $BASE/feedback -H "Authorization: Bearer $KEY" \
     -H 'Content-Type: application/json' \
     -d '{"service": "users-api", "type": "bug", "summary": "500 on project create"}'
   # → {"id": "fb_…", "status": "received"}
   ```
2. **Inspect feedback:**
   ```bash
   curl -H "Authorization: Bearer $KEY" $BASE/feedback/fb_…
   curl -H "Authorization: Bearer $KEY" "$BASE/feedback?service=users-api&type=bug"
   ```
3. **Inspect clusters:**
   ```bash
   curl -H "Authorization: Bearer $KEY" $BASE/clusters
   ```
4. **Change triage status** (`new` → `investigating` → `accepted` /
   `rejected` → `resolved`):
   ```bash
   curl -X PATCH -H "Authorization: Bearer $KEY" \
     -H 'Content-Type: application/json' \
     -d '{"status": "investigating"}' $BASE/feedback/fb_…
   ```

## Seed the A/B/C sample

```bash
python service/seed_sample.py http://localhost:8001 dev-key-change-me
```

Three reporters file the same underlying problem (users endpoint has no
pagination) with different summaries; they appear as one cluster with
`count: 3`.

## Triage statuses

A report is NOT automatically a confirmed bug, and neither is a cluster
— a cluster only means "these reports appear related". Statuses:

| Status | Meaning |
|--------|---------|
| `new` | Report has been received. Every report starts here, no matter how many similar reports already exist. |
| `investigating` | Someone is examining the evidence. |
| `accepted` | A maintainer has determined that the issue/capability request is valid. Set only by humans, never by report count. |
| `rejected` | The report was reviewed and determined not to require action. |
| `resolved` | The underlying issue has been addressed. |

A fresh cluster of 37 identical reports has status `new` with breakdown
`{"new": 37}` — volume is signal for prioritization, never confirmation.

## Clusters

Reports group deterministically on `(service, type, HTTP method,
endpoint, missing_capability)` — the free-text summary is deliberately
excluded so different wordings of one problem stay together. Each
cluster exposes `cluster_id`, `service`, `type`, `endpoint`, `count`,
`first_seen`/`last_seen`, unanimous-or-`mixed` `status`, a per-status
breakdown, a representative report, and all member IDs. Every stored
record also carries its own `cluster_id`, derived the same way.

## Privacy model

Ingestion is always request → validation → scrubbing → persistence;
nothing raw reaches the database. Redacted before storage: authorization
headers, bearer/basic credentials, API keys, cookies, passwords,
secrets, access tokens — including nested objects and credential-shaped
string values. Preserved: status codes, counts, `request_id`-style
correlation strings, error names. Operational logs contain only report
ID, type, and service — never payloads. Treat stored reports as
internal data: authenticated access, documented retention, no public
exposure.

## Notes

- Discovery (`GET /.well-known/feedback-protocol`) and `/health` are
  public; everything else requires the API key.
- Secrets (passwords, tokens, keys, cookies, …) are redacted before
  storage — see `service/scrub.py`.
- Reports are never auto-confirmed: triage status starts at `new` and
  only humans move it.
