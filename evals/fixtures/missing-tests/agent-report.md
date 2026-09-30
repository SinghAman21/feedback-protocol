# Refund calculation review — zero-amount edge case

## Goal
Determine whether `calculate_refund_cents(paid_cents, refunded_cents)` documented behavior, including the zero-amount edge case, is trustworthy for an agent issuing refunds.

## Findings
No defect found. Implementation matches documentation. The zero-amount edge case works as documented, but has no automated test — a gap in verification, not a defect in behavior.

## Evidence
- Docs (`api.md`): "`calculate_refund_cents(paid_cents, refunded_cents)` returns the remaining refundable amount. Never negative. Zero-amount refunds are valid and return `0`. Raises `ValueError` for negative amounts or over-refunds."
- Implementation (`refunds.py:6-13`): checks `paid_cents < 0 or refunded_cents < 0` and `refunded_cents > paid_cents` raise `ValueError`, otherwise returns `paid_cents - refunded_cents`.
- Tests (`test_refunds.py`): 4 tests — `test_partial_refund` (1000,400==600), `test_full_refund` (1000,1000==0), `test_over_refund_rejected`, `test_negative_amounts_rejected`. No test calls with `(0,0)` or otherwise exercises the documented zero-amount case.
- Test run: `python3 -m pytest -v` → `4 passed in 0.06s`.
- Manual repro: `calculate_refund_cents(0,0)` → `0`, `calculate_refund_cents(1000,1000)` → `0`, `calculate_refund_cents(1000,400)` → `600`. All match docs.

## Impact
An agent issuing refunds can rely on the behavior: zero-amount refunds return `0` without error, negatives and over-refunds raise `ValueError`, results are never negative. The only risk is regression confidence — a future change breaking `(0,0)` would not be caught by the suite.

## Suggested next step
Add explicit regression tests for `calculate_refund_cents(0,0)==0` and `calculate_refund_cents(1000,0)==1000` to lock in the documented zero-amount behavior. No code or doc fix needed.