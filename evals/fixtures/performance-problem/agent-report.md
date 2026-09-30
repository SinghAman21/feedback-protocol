# Event listing at scale investigation

## Goal
Determine whether a dashboard client can reliably and quickly load recent audit events in production with roughly 100,000 events via GET /api/v1/events.

## Findings
Only one blocking issue found: persistent performance violation. Pagination is supported and functionally correct (limit default 50 max 100, page default 1), no bug or missing feature prevents loading pages, but each page is too slow for dashboard use.

## Evidence
- Docs quote from api.md: `Performance budget: p99 under 500ms for event listing.` Endpoint documented as `GET /api/v1/events` with `limit (optional, default 50, max 100)` and `page (optional, default 1)` returning `200 with {"events": [...], "page": 1, "limit": 50}`.
- Implementation in events.py defines `READ_LATENCY_S = 3` and calls `time.sleep(READ_LATENCY_S)` in `handle_list_events`, synthesizes 100,000 events via `_all_events()`, then slices for pagination.
- Measured behavior with `handle_list_events({'limit': 50, 'page': 1})` retried 3 times to rule out transient slowness: 3.09s, 3.07s, 3.07s, all HTTP 200 with 50 events. Additional check `{'limit': 2, 'page': 2}` returned HTTP 200 in 3.08s with `evt_2, evt_3`, confirming pagination works but is equally slow regardless of page size.
- Tests in test_events.py cover 200 status, first/second page, and default limit 50, but assert no timing.

## Impact
Dashboard cannot meet 500ms budget; loading even one page of recent events blocks ~3s, ~6x over budget, consistently across retries. At scale this makes quick browsing of 100k events unusable.

## Suggested next step
Service maintainers should reduce per-request latency for event listing to meet stated p99 budget; no client workaround avoids the server-side delay since all pages incur the same cost.