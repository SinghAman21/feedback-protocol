# Refunds

`calculate_refund_cents(paid_cents, refunded_cents)` returns the
remaining refundable amount.

- Never negative.
- Zero-amount refunds are valid and return `0`.
- Raises `ValueError` for negative amounts or over-refunds.
