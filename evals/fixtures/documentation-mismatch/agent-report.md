# User Deletion Investigation — Documented DELETE Does Not Work

## Goal
Determine whether an agent following `api.md` can reliably delete a user via `DELETE /api/v1/users/{id}`.

## Findings
No. Following the documentation fails deterministically. The documented endpoint `DELETE /api/v1/users/{id}` is not routed and returns `404 {"error": "unknown_route"}`. The only working deletion path is the undocumented `POST /api/v1/users/{id}/delete`, which returns `200 {"deleted": "<id>"}`. This is a documentation mismatch (docs contradict behavior and tests codify the contradictory behavior).

## Evidence
- Doc promise (`api.md:3-10`): `DELETE /api/v1/users/{id}` → `200 {"deleted": "<id>"}` on success, `404 {"error": "not_found"}` for unknown id. Example: `DELETE /api/v1/users/u1`.
- Implementation (`users.py:7-12`): `ROUTES` contains `(\"POST\", \"/api/v1/users/{id}/delete\")` for `delete_user`; there is no `(\"DELETE\", \"/api/v1/users/{id}\")` entry. Fallthrough returns `404 {"error": "unknown_route"}`.
- Repro (`python3 -c \"from users import dispatch\"`): `dispatch('DELETE','/api/v1/users/u1')` → `(404, '{\"error\": \"unknown_route\"}')`; `dispatch('POST','/api/v1/users/u1/delete')` → `(200, '{\"deleted\": \"u1\"}')`.
- Tests (`test_users.py:14-22`): `test_delete_user_via_post` asserts POST deletion succeeds; `test_unknown_route_is_404` asserts `DELETE /api/v1/users/u1` returns 404. Suite: `3 passed`.
- Retry / input error ruled out: path spelling matches docs exactly, user `u1` exists in `_USERS`, result is deterministic, not transient.

## Impact
An agent doing exactly what the docs say can never delete a user — every documented DELETE fails with `unknown_route` instead of the promised `deleted` or `not_found`. Automation built on the docs will report failure or retry forever, while the real capability is hidden under an undocumented POST path.

## Suggested next step
Do not change caller code to guess the POST path; fix the contract: either implement `DELETE /api/v1/users/{id}` to match `api.md`, or update `api.md` to document `POST /api/v1/users/{id}/delete` as the supported deletion method and deprecate the DELETE description.