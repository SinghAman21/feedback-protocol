# Member removal investigation: removing 500 members quickly

## Goal
Determine the fastest reliable way to remove 500 members via `DELETE /api/v1/members/{id}`.

## Findings
No reportable API bug, missing feature, documentation mismatch, or performance issue. The only blockers to fast bulk removal are explicitly documented intentional limitations, which per the Feedback Protocol must not be reported.

## Evidence
- Docs (`api.md`): "Remove exactly one member. Bulk delete is **not supported** by design: removal requires per-member audit approval, so deletions happen one at a time."
- Docs (`api.md`): "Rate limiting: 100 requests/minute per workspace. This limit is intentional abuse protection, not a defect. `429` responses include `retry_after_s`."
- Implementation (`members.py:14-20`): `remove_member()` removes one id, enforces `RATE_LIMIT_PER_MINUTE = 100` sliding window, returns `429 {"error": "rate_limited", "retry_after_s": 60}` when exceeded, `404 {"error": "not_found"}` for unknown id — matching docs exactly.
- Tests (`test_members.py`): 2 passed (`test_remove_one_member`, `test_unknown_member_is_404`); manual repro `remove_member('m0')` returned `(200, '{"removed": "m0"}')`.
- Math: 500 sequential single deletes at 100/min requires minimum ~5 minutes plus backoff on 429s.

## Impact
500 members cannot be removed quickly; the reliable path is sequential single deletes respecting 429/retry_after_s, taking >=5 minutes. This is expected behavior, not a defect.

## Suggested next step
Do not file feedback. Implement sequential deletion with rate-limit handling (sleep on 429 per `retry_after_s`), and if faster bulk removal is needed, request a design exception through product channels — not as a protocol bug report.