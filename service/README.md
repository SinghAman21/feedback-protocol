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

## Notes

- Discovery (`GET /.well-known/feedback-protocol`) and `/health` are
  public; everything else requires the API key.
- Secrets (passwords, tokens, keys, cookies, …) are redacted before
  storage — see `service/scrub.py`.
- Reports are never auto-confirmed: triage status starts at `new` and
  only humans move it.
